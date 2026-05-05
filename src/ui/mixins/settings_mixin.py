"""
SettingsMixin — Settings Mixin methods.

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

import os, json, subprocess, threading, time, shutil, tempfile, re

from src.i18n.engine import (
    translate as _T, register_widget as _reg,
    _CURRENT_LANG, _get_khmer_font, _REGISTRY as _I18N_REGISTRY,
)
from src.i18n.translations import TRANSLATIONS
from src.core.config import load_config, save_config
from src.automation.url_normalizer import normalize_facebook_url, URL_TYPE_LABELS as _URL_TYPE_LABELS
from src.core.config import CONFIG_FILE

# Project root — 3 levels up from src/ui/mixins/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.core.subprocess_utils import safe_subprocess_run
# DeviceWorker lazy-imported in methods that use it (saves 117ms cold-start)

class SettingsMixin:
    """Mixin — methods are injected into MainWindow via multiple inheritance."""

    def browse_apk(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Facebook Lite APK", "", "APK Files (*.apk)")
        if file:
            self.apk_input.setText(file)


    def browse_apk_orig(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Facebook Original APK", "", "APK Files (*.apk);;All Files (*)")
        if file:
            self.apk_orig_input.setText(file)


    def open_advanced_config_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("adv_title"))
        dialog.setFixedWidth(900)
        dialog.setStyleSheet("QDialog { background: #1e1e1e; }")

        root = QVBoxLayout(dialog)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        _sec_style = "color: #555555; font-size: 10px; font-weight: bold; letter-spacing: 0.8px; background: transparent; padding-bottom: 4px;"
        _green  = "QPushButton { background: #4CAF50; color: #fff; border: none; border-radius: 6px; font-size: 12px; font-weight: bold; padding: 0 14px; } QPushButton:hover { background: #45a049; } QPushButton:pressed { background: #3d8b40; }"
        _ghost  = "QPushButton { background: #252526; color: #aaaaaa; border: 1px solid #3d3d3d; border-radius: 6px; font-size: 12px; padding: 0 14px; } QPushButton:hover { border-color: #4CAF50; color: #ffffff; }"
        _danger = "QPushButton { background: #252526; color: #f44336; border: 1px solid #3d3d3d; border-radius: 6px; font-size: 12px; padding: 0 14px; } QPushButton:hover { background: #f44336; color: #ffffff; border-color: #f44336; }"
        _lang_active_s   = "QPushButton { background: #4CAF50; color: #fff; border: none; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 2px 10px; }"
        _lang_inactive_s = "QPushButton { background: #2d2d2d; color: #888; border: 1px solid #3d3d3d; border-radius: 4px; font-size: 11px; padding: 2px 10px; } QPushButton:hover { color: #fff; border-color: #4CAF50; }"

        # ── Header ────────────────────────────────────────────────────────
        hdr = QFrame(); hdr.setObjectName("acHdr"); hdr.setFixedHeight(52)
        hdr.setStyleSheet("QFrame#acHdr { background: #252526; border: none; border-bottom: 1px solid #2a2a2a; }")
        hdr_l = QHBoxLayout(hdr); hdr_l.setContentsMargins(20, 0, 20, 0); hdr_l.setSpacing(10)
        hdr_ico = QLabel(); hdr_ico.setPixmap(qta.icon('fa5s.sliders-h', color='#4CAF50').pixmap(14, 14)); hdr_ico.setStyleSheet("background: transparent;")
        hdr_l.addWidget(hdr_ico)
        hdr_ttl = QLabel(_T("adv_title")); hdr_ttl.setStyleSheet("color: #cccccc; font-size: 13px; font-weight: bold; background: transparent;")
        hdr_l.addWidget(hdr_ttl); hdr_l.addStretch()
        # Language buttons — sync with global lang switcher
        dlg_lang_btns = {}
        for lng in ["EN", "ខ្មែរ", "VI"]:
            lb = QPushButton(lng); lb.setFixedHeight(26)
            lb.setStyleSheet(_lang_active_s if lng == _CURRENT_LANG[0] else _lang_inactive_s)
            hdr_l.addWidget(lb)
            dlg_lang_btns[lng] = lb
        root.addWidget(hdr)

        # ── 3-panel body ──────────────────────────────────────────────────
        panels_widget = QWidget(); panels_widget.setStyleSheet("background: #1e1e1e;")
        panels_l = QHBoxLayout(panels_widget); panels_l.setContentsMargins(0, 0, 0, 0); panels_l.setSpacing(0)

        def _make_panel(border_right=True):
            p = QFrame()
            border = "border-right: 1px solid #2a2a2a;" if border_right else ""
            p.setStyleSheet(f"QFrame {{ background: #1e1e1e; {border} }}")
            pl = QVBoxLayout(p); pl.setContentsMargins(18, 18, 18, 18); pl.setSpacing(8)
            return p, pl

        p1, p1l = _make_panel(True)
        p2, p2l = _make_panel(True)
        p3, p3l = _make_panel(False)
        panels_l.addWidget(p1, 1); panels_l.addWidget(p2, 1); panels_l.addWidget(p3, 1)
        root.addWidget(panels_widget, 1)

        # Track widgets for in-dialog language refresh
        _dlg_widgets = []  # (widget, key, "sec"|"btn")

        def _sec_label(layout, key):
            lbl = QLabel(_T(key)); lbl.setStyleSheet(_sec_style)
            layout.addWidget(lbl); _dlg_widgets.append((lbl, key, "sec")); return lbl

        def _btn(layout, icon, key, style, slot):
            b = QPushButton(f"  {_T(key)}")
            ic = '#ffffff' if 'background: #4CAF50' in style else ('#f44336' if 'color: #f44336' in style else '#aaaaaa')
            b.setIcon(qta.icon(icon, color=ic)); b.setFixedHeight(36); b.setStyleSheet(style)
            b.clicked.connect(slot); layout.addWidget(b); _dlg_widgets.append((b, key, "btn")); return b

        # Panel 1 — Facebook App
        _sec_label(p1l, "adv_fb_section")
        _btn(p1l, 'fa5s.broom',     'adv_clear_cache', _ghost,  self._clear_fb_cache)
        _btn(p1l, 'fa5s.trash-alt', 'adv_uninstall',   _danger, self._uninstall_fb)
        _btn(p1l, 'fa5s.download',  'adv_install',     _green,  self._install_fb)
        _btn(p1l, 'fa5s.sync-alt',  'adv_reinstall',   _ghost,  self._reinstall_fb)
        p1l.addStretch()

        # Panel 2 — ADB Tools + VPN
        _sec_label(p2l, "adv_adb_section")
        _btn(p2l, 'fa5s.plug',       'adv_restart_adb', _ghost, self._restart_adb)
        _btn(p2l, 'fa5s.mobile-alt', 'adv_reboot',      _ghost, self._reboot_device)
        div2 = QFrame(); div2.setFixedHeight(1); div2.setStyleSheet("background: #2a2a2a;"); p2l.addWidget(div2)
        _sec_label(p2l, "adv_vpn_section")
        _btn(p2l, 'fa5s.cloud-download-alt', 'adv_backup_vpn',  _ghost, self._backup_vpn_profiles)
        _btn(p2l, 'fa5s.cloud-upload-alt',   'adv_restore_vpn', _ghost, self._restore_vpn_profiles)
        _btn(p2l, 'fa5s.network-wired',      'adv_check_ip',    _ghost, self._check_ip)
        p2l.addStretch()

        # Panel 3 — Device Tools
        _sec_label(p3l, "adv_device_section")
        _btn(p3l, 'fa5s.home',  'adv_home_screen',   _ghost, self._go_home_screen)
        _btn(p3l, 'fa5s.broom', 'adv_clear_recents', _ghost, self._clear_recents)
        
        # Auto Load Device checkbox
        auto_load_container = QWidget()
        auto_load_layout = QHBoxLayout(auto_load_container)
        auto_load_layout.setContentsMargins(0, 8, 0, 0)
        auto_load_layout.setSpacing(8)
        
        auto_load_checkbox = QCheckBox(_T("adv_auto_load_device"))
        auto_load_checkbox.setStyleSheet("""
            QCheckBox {
                color: #cccccc;
                font-size: 12px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #3d3d3d;
                border-radius: 4px;
                background: #1e1e1e;
            }
            QCheckBox::indicator:checked {
                background: #4CAF50;
                border-color: #4CAF50;
            }
        """)
        
        # Load saved state
        config = load_config()
        auto_load_checkbox.setChecked(config.get('auto_load_device', False))
        
        # Save on change
        def save_auto_load_state(checked):
            config = load_config()
            config['auto_load_device'] = checked
            save_config(config)
            self.add_activity(f"✓ Auto Load Device: {'Enabled' if checked else 'Disabled'}")
        
        auto_load_checkbox.stateChanged.connect(lambda state: save_auto_load_state(state == 2))
        
        auto_load_layout.addWidget(auto_load_checkbox)
        auto_load_layout.addStretch()
        p3l.addWidget(auto_load_container)
        _dlg_widgets.append((auto_load_checkbox, "adv_auto_load_device", "btn"))

        # Auto Restart Screen checkbox
        auto_restart_container = QWidget()
        auto_restart_layout = QHBoxLayout(auto_restart_container)
        auto_restart_layout.setContentsMargins(0, 4, 0, 0)
        auto_restart_layout.setSpacing(8)

        auto_restart_checkbox = QCheckBox("Auto Restart Opening Screen")
        auto_restart_checkbox.setStyleSheet(auto_load_checkbox.styleSheet())

        auto_restart_checkbox.setChecked(config.get('auto_restart_screen', True))

        def save_auto_restart_state(checked):
            cfg = load_config()
            cfg['auto_restart_screen'] = checked
            save_config(cfg)
            self.add_activity(f"✓ Auto Restart Screen: {'Enabled' if checked else 'Disabled'}")

        auto_restart_checkbox.stateChanged.connect(lambda state: save_auto_restart_state(state == 2))

        auto_restart_layout.addWidget(auto_restart_checkbox)
        auto_restart_layout.addStretch()
        p3l.addWidget(auto_restart_container)

        p3l.addStretch()

        # ── Footer ────────────────────────────────────────────────────────
        ftr = QFrame(); ftr.setObjectName("acFtr"); ftr.setFixedHeight(52)
        ftr.setStyleSheet("QFrame#acFtr { background: #252526; border: none; border-top: 1px solid #2a2a2a; }")
        ftr_l = QHBoxLayout(ftr); ftr_l.setContentsMargins(20, 0, 20, 0); ftr_l.addStretch()
        close_btn = QPushButton(_T("btn_close")); close_btn.setFixedHeight(32)
        close_btn.setStyleSheet(_ghost); close_btn.clicked.connect(dialog.accept)
        _dlg_widgets.append((close_btn, "btn_close", "btn"))
        ftr_l.addWidget(close_btn); root.addWidget(ftr)

        # ── Language switcher — updates both global + dialog ──────────────
        def _dlg_switch_lang(lng):
            apply_language(lng)
            from PyQt6.QtGui import QFont as _QFont
            if lng == "ខ្មែរ":
                _fname, _fsize = _get_khmer_font(), 24
            else:
                _fname, _fsize = "Segoe UI", 12
            if hasattr(self, 'tab_widget'):
                _tab_keys = ["tab_dashboard", "tab_custom", "tab_settings"]
                for i, k in enumerate(_tab_keys):
                    if i < self.tab_widget.count():
                        self.tab_widget.setTabText(i, _T(k))
                # Apply font to main window tab bar
                if lng == "ខ្មែរ":
                    self.tab_widget.tabBar().setFont(_QFont(_get_khmer_font(), 14))
                else:
                    self.tab_widget.tabBar().setFont(_QFont("Segoe UI", 10))
            if hasattr(self, '_lang_btns'):
                # Dynamic font size for language buttons
                for l, b in self._lang_btns.items():
                    btn_fsize = "16px" if l == "ខ្មែរ" else "10px"
                    _la = f"QPushButton{{background:#4CAF50;color:#fff;border:none;border-radius:3px;font-size:{btn_fsize};font-weight:bold;padding:2px 8px;}}QPushButton:hover{{background:#45a049;}}"
                    _li = f"QPushButton{{background:#2a2a2a;color:#666;border:1px solid #3d3d3d;border-radius:3px;font-size:{btn_fsize};padding:2px 8px;}}QPushButton:hover{{color:#fff;border-color:#4CAF50;}}"
                    b.setStyleSheet(_la if l == lng else _li)
                    if l == "ខ្មែរ":
                        b.setFont(_QFont(_get_khmer_font(), 16))
            hdr_ttl.setText(_T("adv_title"))
            hdr_ttl.setFont(_QFont(_fname, _fsize))
            dialog.setWindowTitle(_T("adv_title"))
            for widget, key, wtype in _dlg_widgets:
                try:
                    widget.setText(_T(key) if wtype == "sec" else f"  {_T(key)}")
                    widget.setFont(_QFont(_fname, _fsize))
                except RuntimeError:
                    pass
            for l, b in dlg_lang_btns.items():
                b.setStyleSheet(_lang_active_s if l == lng else _lang_inactive_s)

        for lng in ["EN", "ខ្មែរ", "VI"]:
            dlg_lang_btns[lng].clicked.connect(lambda checked, l=lng: _dlg_switch_lang(l))

        dialog.exec()


    def _adb(self, args):
        """Run an ADB command and return output."""
        adb = r"C:\Users\KLS COMPUTER\Desktop\FRT\platform-tools\adb.exe"
        devices = [cb.text() for cb in self.device_checkboxes if cb.isChecked()] if self.device_checkboxes else ["29ba10487d2b"]
        results = []
        for dev in devices:
            result = safe_subprocess_run([adb, "-s", dev] + args, capture_output=True)
            out = result.stdout if isinstance(result.stdout, str) else result.stdout.decode("utf-8", errors="replace")
            err = result.stderr if isinstance(result.stderr, str) else result.stderr.decode("utf-8", errors="replace")
            text = (out.strip() or err.strip()).replace("\r\n", "\n").replace("\r", "\n")
            results.append(f"{dev}: {text}")
        return "\n".join(results)


    def _get_fb_package(self):
        pkg_map = {"Facebook Lite": "com.facebook.lite", "Facebook (Original)": "com.facebook.katana", "Messenger": "com.facebook.orca"}
        return pkg_map.get(self.app_selection_input.currentText(), "com.facebook.lite")


    def _clear_fb_cache(self):
        pkg = self._get_fb_package()
        out = self._adb(["shell", "pm", "clear", pkg])
        self.add_activity(f"Cache cleared: {pkg}")
        QMessageBox.information(self, "Clear Cache", out)


    def _uninstall_fb(self):
        pkg = self._get_fb_package()
        if QMessageBox.question(self, "Uninstall", f"Uninstall {pkg}?") != QMessageBox.StandardButton.Yes:
            return
        out = self._adb(["uninstall", pkg])
        self.add_activity(f"Uninstalled: {pkg}")
        QMessageBox.information(self, "Uninstall", out)


    def _install_fb(self):
        import os, glob, threading
        pkg = self._get_fb_package()
        adb = r"C:\Users\KLS COMPUTER\Desktop\FRT\platform-tools\adb.exe"
        devices = [cb.text() for cb in self.device_checkboxes if cb.isChecked()] if self.device_checkboxes else ["29ba10487d2b"]

        # Pick APK path based on selected app
        if pkg == "com.facebook.lite":
            apk = self.apk_input.text().strip()
        else:
            apk = getattr(self, 'apk_orig_input', None)
            apk = apk.text().strip() if apk else self.apk_input.text().strip()

        self.add_activity(f"Installing {pkg}...")

        def _run():
            results = []
            for dev in devices:
                if apk and os.path.isdir(apk):
                    apk_files = glob.glob(os.path.join(apk, "*.apk"))
                    if not apk_files:
                        results.append(f"{dev}: No APK files found in folder"); continue
                    result = safe_subprocess_run([adb, "-s", dev, "install-multiple", "-r"] + apk_files, capture_output=True)
                    results.append(f"{dev}: {result.stdout.strip() or result.stderr.strip()}")
                elif apk and os.path.isfile(apk):
                    result = safe_subprocess_run([adb, "-s", dev, "install", "-r", apk], capture_output=True)
                    results.append(f"{dev}: {result.stdout.strip() or result.stderr.strip()}")
                else:
                    results.append(self._pull_and_reinstall(dev, pkg, adb))
            out = "\n".join(results)
            self.add_activity(f"Installed: {pkg}")
            self._install_result_signal.emit(pkg, out)

        threading.Thread(target=_run, daemon=True).start()


    def _show_install_result(self, pkg, out):
        msg = QMessageBox(self)
        msg.setWindowTitle("Install Result")
        msg.setText(f"Package: {pkg}")
        msg.setInformativeText(out[:300] if len(out) <= 300 else out[:300] + "...")
        msg.setDetailedText(out)
        msg.exec()


    def _pull_and_reinstall(self, device, pkg, adb):
        """Pull APKs from device, uninstall, then reinstall — works for split APKs like Katana."""
        import tempfile, os
        log = []
        try:
            # Get APK paths on device
            r = safe_subprocess_run([adb, "-s", device, "shell", "pm", "path", pkg], capture_output=True)
            lines = [l.strip() for l in r.stdout.strip().splitlines() if l.startswith("package:")]
            if not lines:
                return f"{device}: App not found on device"
            remote_paths = [l.replace("package:", "") for l in lines]
            log.append(f"Found {len(remote_paths)} APK(s) on device")

            # Pull to temp folder
            tmp = tempfile.mkdtemp(prefix="fb_apks_")
            local_apks = []
            for i, rp in enumerate(remote_paths):
                local = os.path.join(tmp, f"split_{i}.apk")
                pull_r = safe_subprocess_run([adb, "-s", device, "pull", rp, local], capture_output=True)
                size = os.path.getsize(local) if os.path.exists(local) else 0
                log.append(f"Pull {i+1}: {os.path.basename(rp)} ({size//1024}KB)")
                if size > 0:
                    local_apks.append(local)

            if not local_apks:
                return "\n".join(log) + "\nFailed to pull APKs"

            # Uninstall
            u = safe_subprocess_run([adb, "-s", device, "uninstall", pkg], capture_output=True)
            log.append(f"Uninstall: {u.stdout.strip() or u.stderr.strip()}")

            # Reinstall (no -t flag — avoid test APK issues on production devices)
            result = safe_subprocess_run([adb, "-s", device, "install-multiple", "-r"] + local_apks, capture_output=True)
            raw = result.stdout if isinstance(result.stdout, str) else result.stdout.decode("utf-8", errors="replace")
            raw = raw.strip().replace("\r\n", "\n").replace("\r", "\n")
            if not raw:
                raw = result.stderr if isinstance(result.stderr, str) else result.stderr.decode("utf-8", errors="replace")
                raw = raw.strip()
            log.append(f"Install: {raw}")

            # If install succeeded, force launcher to show the app
            if "success" in raw.lower():
                safe_subprocess_run([adb, "-s", device, "shell", "pm", "enable", pkg], capture_output=True)
                # Kill launcher so it rescans on next open
                safe_subprocess_run([adb, "-s", device, "shell",
                    "am", "force-stop", "com.sec.android.app.launcher"], capture_output=True)
                safe_subprocess_run([adb, "-s", device, "shell",
                    "am", "force-stop", "com.google.android.apps.nexuslauncher"], capture_output=True)
                safe_subprocess_run([adb, "-s", device, "shell",
                    "am", "force-stop", "com.android.launcher3"], capture_output=True)
                log.append("Launcher refreshed — open your app drawer to see the app")

            # Cleanup
            for f in local_apks:
                try: os.remove(f)
                except: pass
            try: os.rmdir(tmp)
            except: pass

            return "\n".join(log)
        except Exception as e:
            return "\n".join(log) + f"\nError: {e}"


    def _reinstall_fb(self):
        import threading
        pkg = self._get_fb_package()
        adb = r"C:\Users\KLS COMPUTER\Desktop\FRT\platform-tools\adb.exe"
        devices = [cb.text() for cb in self.device_checkboxes if cb.isChecked()] if self.device_checkboxes else ["29ba10487d2b"]

        self.add_activity(f"Reinstalling {pkg}...")

        def _run():
            results = [self._pull_and_reinstall(dev, pkg, adb) for dev in devices]
            out = "\n\n".join(results)
            self.add_activity(f"Reinstalled: {pkg}")
            self._install_result_signal.emit(pkg, out)

        threading.Thread(target=_run, daemon=True).start()


    def _restart_adb(self):
        adb = r"C:\Users\KLS COMPUTER\Desktop\FRT\platform-tools\adb.exe"
        safe_subprocess_run([adb, "kill-server"], capture_output=True)
        safe_subprocess_run([adb, "start-server"], capture_output=True)
        self.add_activity("ADB server restarted")
        QMessageBox.information(self, "ADB", "ADB server restarted.")


    def _reboot_device(self):
        out = self._adb(["reboot"])
        self.add_activity("Device reboot triggered")
        QMessageBox.information(self, "Reboot", out)


    def _browse_vpn_config(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select VPN Config", "", "OpenVPN Config (*.ovpn *.conf);;All Files (*)")
        if file:
            self.vpn_config_input.setText(file)


    def _browse_vpn_file(self):
        """Browse for VPN file from vpn folder"""
        vpn_dir = os.path.join(_PROJECT_ROOT, "vpn")
        file, _ = QFileDialog.getOpenFileName(self, "Select VPN File", vpn_dir, "OpenVPN Config (*.ovpn);;All Files (*)")
        if file:
            self.vpn_file_input.setText(file)


    def _backup_vpn_profiles(self):
        """Backup OpenVPN profiles from phone to PC (vpn_backup/ folder)."""
        import threading, os as _os
        adb = r"C:\Users\KLS COMPUTER\Desktop\FRT\platform-tools\adb.exe"
        adb_id = "29ba10487d2b"
        backup_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "vpn_backup")
        try:
            _os.makedirs(backup_dir, exist_ok=True)
        except PermissionError:
            QMessageBox.warning(self, "Permission Error", 
                f"Cannot create backup folder:\n{backup_dir}\n\nRun as Administrator or create the folder manually.")
            return

        def _run():
            # Copy OpenVPN data to accessible location then pull
            safe_subprocess_run([adb, "-s", adb_id, "shell",
                "su -c 'cp -r /data/user/0/de.blinkt.openvpn /data/local/tmp/openvpn_bak && chmod -R 777 /data/local/tmp/openvpn_bak'"],
                capture_output=True)
            r = safe_subprocess_run([adb, "-s", adb_id, "pull", "/data/local/tmp/openvpn_bak", backup_dir],
                capture_output=True)
            safe_subprocess_run([adb, "-s", adb_id, "shell", "rm -rf /data/local/tmp/openvpn_bak"], capture_output=True)
            if r.returncode == 0:
                self._vpn_signal.emit("log", f"Backup saved to vpn_backup/")
            else:
                self._vpn_signal.emit("log", f"Backup failed: {r.stderr}")

        threading.Thread(target=_run, daemon=True).start()
        QMessageBox.information(self, "VPN Backup", f"Backing up OpenVPN profiles to:\n{backup_dir}")


    def _restore_vpn_profiles(self):
        """Restore OpenVPN profiles from PC backup to phone instantly (no UI needed)."""
        import threading, os as _os
        adb = r"C:\Users\KLS COMPUTER\Desktop\FRT\platform-tools\adb.exe"
        adb_id = "29ba10487d2b"
        backup_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "vpn_backup", "openvpn_bak")

        if not _os.path.exists(backup_dir):
            QMessageBox.warning(self, "VPN Restore", "No backup found. Run Backup first."); return

        def _run():
            # Push backup to temp, then restore with root
            safe_subprocess_run([adb, "-s", adb_id, "push", backup_dir, "/data/local/tmp/openvpn_bak"], capture_output=True)
            safe_subprocess_run([adb, "-s", adb_id, "shell",
                "su -c 'cp -r /data/local/tmp/openvpn_bak/. /data/user/0/de.blinkt.openvpn/ && "
                "chown -R u0_a136:u0_a136 /data/user/0/de.blinkt.openvpn/ && "
                "chmod -R 660 /data/user/0/de.blinkt.openvpn/files/ && "
                "chmod -R 660 /data/user/0/de.blinkt.openvpn/shared_prefs/'"],
                capture_output=True)
            safe_subprocess_run([adb, "-s", adb_id, "shell", "rm -rf /data/local/tmp/openvpn_bak"], capture_output=True)
            # Force OpenVPN to reload
            safe_subprocess_run([adb, "-s", adb_id, "shell",
                "am force-stop de.blinkt.openvpn"], capture_output=True)
            self._vpn_signal.emit("log", "Profiles restored. OpenVPN restarted.")

        threading.Thread(target=_run, daemon=True).start()
        QMessageBox.information(self, "VPN Restore",
            "Restoring profiles from backup...\nOpenVPN will restart automatically.")


    def _push_all_vpn_to_phone(self):
        """Push all .ovpn files from selected folder to /sdcard/Download/ on phone."""
        import threading
        adb = r"C:\Users\KLS COMPUTER\Desktop\FRT\platform-tools\adb.exe"

        # Use folder from input if available, fallback to default vpn/
        if hasattr(self, 'vpn_folder_input') and self.vpn_folder_input.text().strip():
            vpn_dir = self.vpn_folder_input.text().strip()
        else:
            vpn_dir = os.path.join(_PROJECT_ROOT, "vpn")

        if not os.path.exists(vpn_dir):
            QMessageBox.warning(self, "VPN", f"vpn/ folder not found:\n{vpn_dir}"); return

        files = [f for f in os.listdir(vpn_dir) if f.endswith(".ovpn")]
        if not files:
            QMessageBox.warning(self, "VPN", "No .ovpn files found in vpn/ folder"); return

        self.add_activity(f"Pushing {len(files)} VPN files to phone /data/local/tmp/vpn/...")

        def _run():
            adb_id = "29ba10487d2b"
            ok = 0
            # Ensure destinations exist
            safe_subprocess_run([adb, "-s", adb_id, "shell", "mkdir -p /data/local/tmp/vpn"], capture_output=True)
            safe_subprocess_run([adb, "-s", adb_id, "shell", "su -c 'mkdir -p /sdcard/Download/vpn'"], capture_output=True)
            for fname in files:
                local_path = os.path.join(vpn_dir, fname)
                # Push with original filename (keep spaces) — shell scripts will quote properly
                r = safe_subprocess_run(
                    [adb, "-s", adb_id, "push", local_path, f"/data/local/tmp/vpn/{fname}"],
                    capture_output=True
                )
                if r.returncode == 0:
                    # Also copy to /sdcard/Download/vpn/ using root (quote filename for shell)
                    safe_subprocess_run([adb, "-s", adb_id, "shell",
                        f"su -c 'cp \"/data/local/tmp/vpn/{fname}\" \"/sdcard/Download/vpn/{fname}\"'"],
                        capture_output=True
                    )
                    ok += 1
                else:
                    self._vpn_signal.emit("log", f"Push failed: {fname}")
            self._vpn_signal.emit("log", f"Pushed {ok}/{len(files)} files to /data/local/tmp/vpn/ and /sdcard/Download/vpn/")

        threading.Thread(target=_run, daemon=True).start()
        QMessageBox.information(self, "VPN",
            f"Pushing {len(files)} files to /data/local/tmp/vpn/...\n\nCheck Activity Log for progress.")


    def _push_vpn_file(self):
        """Import ALL .ovpn files into OpenVPN via UI automation (one by one until completion)."""
        import threading, time, os as _os
        adb = r"C:\Users\KLS COMPUTER\Desktop\FRT\platform-tools\adb.exe"

        if hasattr(self, 'vpn_folder_input') and self.vpn_folder_input.text().strip():
            vpn_dir = self.vpn_folder_input.text().strip()
        else:
            vpn_dir = _os.path.join(_PROJECT_ROOT, "vpn")

        if not _os.path.exists(vpn_dir):
            QMessageBox.warning(self, "VPN", f"vpn/ folder not found:\n{vpn_dir}"); return

        files = sorted([f for f in _os.listdir(vpn_dir) if f.endswith(".ovpn")])
        if not files:
            QMessageBox.warning(self, "VPN", "No .ovpn files found in vpn/ folder"); return

        self.add_activity(f"Importing {len(files)} VPN profiles via UI automation (one by one)...")

        def _run():
            adb_id = "29ba10487d2b"
            import re as _re

            # Check existing profiles to skip already imported ones
            xml_r = safe_subprocess_run([adb, "-s", adb_id, "shell",
                "su -c 'ls /data/user/0/de.blinkt.openvpn/files/*.cp 2>/dev/null | wc -l'"],
                capture_output=True)
            existing_count = int((xml_r.stdout or "0").strip())
            
            self._vpn_signal.emit("log", f"Already imported: {existing_count} profiles")
            
            # Get list of existing .cp files to skip
            cp_list_r = safe_subprocess_run([adb, "-s", adb_id, "shell",
                "su -c 'ls /data/user/0/de.blinkt.openvpn/files/*.cp 2>/dev/null'"],
                capture_output=True)
            existing_uuids = set()
            if cp_list_r.stdout:
                for line in cp_list_r.stdout.strip().split('\n'):
                    if line.strip():
                        existing_uuids.add(line.strip().split('/')[-1].replace('.cp', ''))

            # Get profile names from VPN.xml to check what's already imported
            xml_r = safe_subprocess_run([adb, "-s", adb_id, "shell",
                "su -c 'cat /data/user/0/de.blinkt.openvpn/shared_prefs/VPN.xml 2>/dev/null'"],
                capture_output=True)
            existing_names = set(_re.findall(r'<string name="mName">([^<]+)</string>', xml_r.stdout or ""))

            def _parse_name(fname):
                name = fname.replace(".ovpn", "")
                if name.startswith("NCVPN-"): name = name[6:]
                if name.endswith("-TCP"): name = name[:-4]
                elif name.endswith("-UDP"): name = name[:-4]
                idx = name.index("-") if "-" in name else -1
                return f"{name[:idx]} - {name[idx+1:]}" if idx > 0 else name

            pending = [f for f in files if _parse_name(f) not in existing_names]
            
            if not pending:
                self._vpn_signal.emit("log", f"All {len(files)} profiles already imported. Nothing to do.")
                return

            self._vpn_signal.emit("log", f"Need to import {len(pending)} profiles (skipping {len(files)-len(pending)} already done)")

            # Grant storage permissions once
            safe_subprocess_run([adb, "-s", adb_id, "shell",
                "pm grant de.blinkt.openvpn android.permission.READ_EXTERNAL_STORAGE"],
                capture_output=True)
            safe_subprocess_run([adb, "-s", adb_id, "shell",
                "pm grant de.blinkt.openvpn android.permission.WRITE_EXTERNAL_STORAGE"],
                capture_output=True)

            # Open OpenVPN MainActivity once to dismiss permission dialog
            safe_subprocess_run([adb, "-s", adb_id, "shell",
                "am start -n de.blinkt.openvpn/.activities.MainActivity"],
                capture_output=True)
            time.sleep(2)
            
            # Dismiss any permission dialog by tapping "Allow" if present
            safe_subprocess_run([adb, "-s", adb_id, "shell", "input tap 540 1160"],
                capture_output=True)
            time.sleep(1)

            # Process each file one by one
            imported_count = 0
            for idx, fname in enumerate(pending, 1):
                # Fire ConfigConverter intent
                safe_subprocess_run([adb, "-s", adb_id, "shell",
                    f'am start -n de.blinkt.openvpn/.activities.ConfigConverter '
                    f'-a android.intent.action.VIEW '
                    f'-d "file:///data/local/tmp/vpn/{fname}" '
                    f'-t application/x-openvpn-profile'],
                    capture_output=True)
                
                time.sleep(3)  # Wait for ConfigConverter to load
                
                # Tap save button at (987, 1726) — the ImageButton in ConfigConverter
                safe_subprocess_run([adb, "-s", adb_id, "shell", "input tap 987 1726"],
                    capture_output=True)
                
                time.sleep(2)  # Wait for save to complete
                
                # Go back to close ConfigConverter
                safe_subprocess_run([adb, "-s", adb_id, "shell", "input keyevent KEYCODE_BACK"],
                    capture_output=True)
                
                time.sleep(0.5)
                
                imported_count += 1
                
                # Log progress every 10 files
                if idx % 10 == 0:
                    self._vpn_signal.emit("log", f"Progress: {idx}/{len(pending)} profiles imported...")

            # Count final .cp files
            final_r = safe_subprocess_run([adb, "-s", adb_id, "shell",
                "su -c 'ls /data/user/0/de.blinkt.openvpn/files/*.cp 2>/dev/null | wc -l'"],
                capture_output=True)
            final_count = int((final_r.stdout or "0").strip())

            self._vpn_signal.emit("log", 
                f"Done. Processed {imported_count} files. Total profiles in OpenVPN: {final_count}")

        threading.Thread(target=_run, daemon=True).start()
        QMessageBox.information(self, "VPN Import",
            f"Importing {len(files)} profiles via UI automation.\n\n"
            f"This will take ~6 seconds per file ({len(files)*6//60} minutes total).\n"
            f"Check Activity Log for progress.")




    def _import_multiple_vpn_files(self):
        """Let user pick specific .ovpn files and import them into OpenVPN via UI automation."""
        import threading, time, os as _os, re as _re

        vpn_dir = _os.path.join(_PROJECT_ROOT, "vpn")
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select OVPN Files to Import", vpn_dir,
            "OpenVPN Config (*.ovpn);;All Files (*)"
        )
        if not files:
            return

        adb = self.adb_path
        devices = [cb.text() for cb in self.device_checkboxes if cb.isChecked()]
        if not devices:
            QMessageBox.warning(self, "No Device", "No device selected in Device Settings.")
            return

        fnames = [_os.path.basename(f) for f in files]
        self.add_activity(f"Importing {len(files)} selected VPN file(s) on {len(devices)} device(s)...")

        def _run():
            import concurrent.futures

            def _run_device(dev):
                self.add_activity(f"--- Device: {dev} ---")

                safe_subprocess_run([adb, "-s", dev, "shell",
                    "mkdir -p /data/local/tmp/vpn"], capture_output=True)

                for fp in files:
                    fname = _os.path.basename(fp)
                    dest = f"/data/local/tmp/vpn/{fname}"
                    try:
                        subprocess.run([adb, "-s", dev, "push", fp, dest],
                            capture_output=True, timeout=20)
                        subprocess.run([adb, "-s", dev, "shell", f"chmod 644 {dest}"],
                            capture_output=True, timeout=5)
                    except Exception as e:
                        self.add_activity(f"✗ Push failed {fname}: {e}")

                subprocess.run([adb, "-s", dev, "shell",
                    "pm grant de.blinkt.openvpn android.permission.READ_EXTERNAL_STORAGE"],
                    capture_output=True, timeout=5)
                subprocess.run([adb, "-s", dev, "shell",
                    "am start -n de.blinkt.openvpn/.activities.MainActivity"],
                    capture_output=True, timeout=5)
                time.sleep(2)
                subprocess.run([adb, "-s", dev, "shell", "input tap 540 1160"],
                    capture_output=True, timeout=3)
                time.sleep(1)

                for fname in fnames:
                    dest = f"/data/local/tmp/vpn/{fname}"
                    self.add_activity(f"→ {fname} on {dev}...")
                    try:
                        subprocess.run([adb, "-s", dev, "shell",
                            f'am start -n de.blinkt.openvpn/.activities.ConfigConverter '
                            f'-a android.intent.action.VIEW '
                            f'-d "file://{dest}" '
                            f'-t application/x-openvpn-profile'],
                            capture_output=True, timeout=5)

                        xml = ""
                        for _wait in range(6):
                            time.sleep(1)
                            try:
                                subprocess.run([adb, "-s", dev, "shell",
                                    "uiautomator dump /sdcard/ui_cv.xml"],
                                    capture_output=True, timeout=8)
                                ui_r = subprocess.run([adb, "-s", dev, "shell", "cat /sdcard/ui_cv.xml"],
                                    capture_output=True, text=True, timeout=5)
                                xml = ui_r.stdout or ""
                                if "EditText" in xml or "Convert Config" in xml:
                                    break
                            except Exception:
                                pass

                        tapped = False
                        m = _re.search(
                            r'class="android\.widget\.ImageButton"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
                        if m:
                            x1,y1,x2,y2 = map(int, m.groups())
                            subprocess.run([adb, "-s", dev, "shell",
                                f"input tap {(x1+x2)//2} {(y1+y2)//2}"],
                                capture_output=True, timeout=3)
                            tapped = True
                        if not tapped:
                            subprocess.run([adb, "-s", dev, "shell", "input tap 987 1726"],
                                capture_output=True, timeout=3)

                        time.sleep(2)
                        subprocess.run([adb, "-s", dev, "shell", "input keyevent KEYCODE_BACK"],
                            capture_output=True, timeout=3)
                        time.sleep(0.5)
                        self.add_activity(f"✓ {fname} on {dev}")
                    except Exception as e:
                        self.add_activity(f"✗ Failed {fname} on {dev}: {e}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=len(devices)) as ex:
                concurrent.futures.wait([ex.submit(_run_device, dev) for dev in devices])

            self.add_activity(f"✓ Done: {len(files)} file(s) on {len(devices)} device(s)")

        threading.Thread(target=_run, daemon=True).start()


    def _connect_vpn(self):
        import threading, random
        adb = r"C:\Users\KLS COMPUTER\Desktop\FRT\platform-tools\adb.exe"
        devices = [cb.text() for cb in self.device_checkboxes if cb.isChecked()] if self.device_checkboxes else ["29ba10487d2b"]

        # Get credentials from dialog inputs if available
        vpn_user = getattr(self, 'vpn_user_input', None)
        vpn_pass = getattr(self, 'vpn_pass_input', None)
        username = vpn_user.text().strip() if vpn_user and vpn_user.text().strip() else "spsahnann@namecheap"
        password = vpn_pass.text().strip() if vpn_pass and vpn_pass.text().strip() else "s30NYSnlUE"

        # Get profile from combo (dialog is still open when this runs)
        vpn_dir = os.path.join(_PROJECT_ROOT, "vpn")
        srv = getattr(self, 'vpn_server_combo', None)
        mode_w = getattr(self, 'vpn_mode_combo', None)
        mode = mode_w.currentText() if mode_w else "Select Location"

        if not srv or srv.count() == 0:
            # Fallback: read from config
            ovpn_files = sorted([f for f in os.listdir(vpn_dir) if f.endswith(".ovpn")]) if os.path.exists(vpn_dir) else []
            if not ovpn_files:
                QMessageBox.warning(self, "VPN", "No .ovpn files found in vpn/ folder."); return
            saved_idx = 0
            try:
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, 'r', encoding='utf-8-sig') as _cf:
                        saved_idx = json.load(_cf).get('vpn_location_index', 0)
            except Exception:
                pass
            if mode == "Random Location":
                saved_idx = random.randint(0, len(ovpn_files) - 1)
            saved_idx = min(saved_idx, len(ovpn_files) - 1)
            profile = ovpn_files[saved_idx]
        else:
            if mode == "Random Location":
                idx = random.randint(0, srv.count() - 1)
            else:
                idx = srv.currentIndex()
            profile = srv.itemData(idx)   # filename
            if not profile:
                QMessageBox.warning(self, "VPN", "No profile selected."); return

        # Build human label from filename
        name = profile.replace(".ovpn", "")
        if name.startswith("NCVPN-"): name = name[6:]
        if name.endswith("-TCP"): name = name[:-4]
        elif name.endswith("-UDP"): name = name[:-4]
        dash = name.index("-") if "-" in name else -1
        label = f"{name[:dash]} - {name[dash+1:]}" if dash > 0 else name

        # Get ovpn file path
        ovpn_file = os.path.join(vpn_dir, profile)
        if not os.path.exists(ovpn_file):
            QMessageBox.warning(self, "VPN", f"OVPN file not found: {profile}"); return

        self.vpn_status_dot.setStyleSheet("background: #FF9800; border-radius: 5px;")
        self.vpn_status_val.setText(f"Connecting: {label}")
        self.vpn_status_val.setStyleSheet("color: #FF9800; font-size: 11px; background: transparent;")
        self.add_activity(f"VPN connecting on phone: {label}")
        if hasattr(self, 'vpn_connect_btn'): self.vpn_connect_btn.setEnabled(False)

        def _run():
            try:
                import time
                for dev in devices:
                    # Step 1: Open MainActivity and check if profile already exists
                    self._vpn_signal.emit("log", "Opening OpenVPN app...")
                    safe_subprocess_run([adb, "-s", dev, "shell",
                        "am start -n de.blinkt.openvpn/.activities.MainActivity"
                    ], capture_output=True)
                    time.sleep(2)

                    # Dump UI to check if profile exists
                    safe_subprocess_run([adb, "-s", dev, "shell", "uiautomator dump /sdcard/ui_check.xml"], capture_output=True)
                    time.sleep(1)
                    
                    # Check if we need to import
                    ui_result = safe_subprocess_run([adb, "-s", dev, "shell", "cat /sdcard/ui_check.xml"], capture_output=True)
                    profile_exists = label in ui_result.stdout if ui_result.stdout else False
                    
                    if not profile_exists:
                        self._vpn_signal.emit("log", f"Profile not found - importing {label}...")
                        
                        # Prepare clean profile name
                        clean_name = label.replace(" ", "_").replace("-", "")
                        
                        # Step 2: Push the ovpn file to phone in a location OpenVPN can access
                        self._vpn_signal.emit("log", f"Copying {os.path.basename(ovpn_file)} to phone...")
                        temp_filename = f"{clean_name}.ovpn"
                        # Use /sdcard/ root instead of /sdcard/Download/
                        temp_path = f"/sdcard/{temp_filename}"
                        safe_subprocess_run([adb, "-s", dev, "push", ovpn_file, temp_path], capture_output=True)
                        time.sleep(1)
                        
                        # Make file world-readable so OpenVPN can access it
                        safe_subprocess_run([adb, "-s", dev, "shell", f"chmod 644 {temp_path}"], capture_output=True)
                        
                        # Step 3: Use intent to directly open the file with OpenVPN
                        self._vpn_signal.emit("log", "Importing profile via intent...")
                        safe_subprocess_run([adb, "-s", dev, "shell",
                            f"am start -a android.intent.action.VIEW -d file://{temp_path} -t application/x-openvpn-profile"
                        ], capture_output=True)
                        time.sleep(3)

                        # Step 3.5: If file picker opened, find and tap the temp file
                        self._vpn_signal.emit("log", f"Looking for {temp_filename}...")
                        safe_subprocess_run([adb, "-s", dev, "shell", "uiautomator dump /sdcard/ui_picker.xml"], capture_output=True)
                        time.sleep(1)
                        
                        ui_result = safe_subprocess_run([adb, "-s", dev, "shell", "cat /sdcard/ui_picker.xml"], capture_output=True)
                        
                        if ui_result.stdout and temp_filename in ui_result.stdout:
                            # File picker is open - find and tap the file
                            import re
                            pattern = f'text="{temp_filename}"[^>]*bounds="\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]"'
                            match = re.search(pattern, ui_result.stdout)
                            
                            if match:
                                x1, y1, x2, y2 = map(int, match.groups())
                                tap_x = (x1 + x2) // 2
                                tap_y = (y1 + y2) // 2
                                self._vpn_signal.emit("log", f"Tapping {temp_filename} at ({tap_x}, {tap_y})")
                                safe_subprocess_run([adb, "-s", dev, "shell", f"input tap {tap_x} {tap_y}"], capture_output=True)
                                time.sleep(3)
                        
                        # Permission dialog may appear - tap "Allow"
                        self._vpn_signal.emit("log", "Checking for permission dialog...")
                        safe_subprocess_run([adb, "-s", dev, "shell", "input tap 360 665"], capture_output=True)
                        time.sleep(2)

                        # Step 4: "Convert Config File" dialog should appear
                        self._vpn_signal.emit("log", "Setting profile name...")
                        
                        # Tap the profile name field
                        safe_subprocess_run([adb, "-s", dev, "shell", "input tap 460 230"], capture_output=True)
                        time.sleep(0.5)
                        
                        # Clear all text
                        safe_subprocess_run([adb, "-s", dev, "shell", "input keyevent KEYCODE_MOVE_HOME"], capture_output=True)
                        time.sleep(0.2)
                        for _ in range(100):
                            safe_subprocess_run([adb, "-s", dev, "shell", "input keyevent KEYCODE_DEL"], capture_output=True)
                            time.sleep(0.02)
                        
                        # Enter clean profile name
                        safe_subprocess_run([adb, "-s", dev, "shell", f"input text {clean_name}"], capture_output=True)
                        time.sleep(0.5)
                        
                        # Find confirm button via UIAutomator XML (avoid hardcoded tap that hits SETTINGS tab)
                        safe_subprocess_run([adb, "-s", dev, "shell", "uiautomator dump /sdcard/ui_confirm.xml"], capture_output=True)
                        time.sleep(1)
                        ui_confirm = safe_subprocess_run([adb, "-s", dev, "shell", "cat /sdcard/ui_confirm.xml"], capture_output=True)
                        confirmed = False
                        if ui_confirm.stdout:
                            import re as _re
                            for btn_pat in [
                                r'content-desc="OK"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                                r'text="OK"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                                r'content-desc="(?:Save|Confirm|Done|Accept)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                                r'class="android\.widget\.ImageButton"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                            ]:
                                m = _re.search(btn_pat, ui_confirm.stdout)
                                if m:
                                    x1, y1, x2, y2 = map(int, m.groups())
                                    tx, ty = (x1+x2)//2, (y1+y2)//2
                                    if not (ty < 100 and tx > 800):
                                        safe_subprocess_run([adb, "-s", dev, "shell", f"input tap {tx} {ty}"], capture_output=True)
                                        confirmed = True
                                        time.sleep(3)
                                        break
                        if not confirmed:
                            safe_subprocess_run([adb, "-s", dev, "shell", "input keyevent KEYCODE_ENTER"], capture_output=True)
                            time.sleep(3)
                        
                        # Clean up temp file
                        safe_subprocess_run([adb, "-s", dev, "shell", f"rm {temp_path}"], capture_output=True)

                        # Profile imported - now edit it
                        self._vpn_signal.emit("log", "Profile imported - adding credentials...")
                        
                        # Tap pencil icon to edit (right side of profile row)
                        safe_subprocess_run([adb, "-s", dev, "shell", "input tap 650 300"], capture_output=True)
                        time.sleep(2)

                        # Scroll down to Authentication section
                        for _ in range(5):
                            safe_subprocess_run([adb, "-s", dev, "shell", "input swipe 360 800 360 300"], capture_output=True)
                            time.sleep(0.3)

                        # Enter username
                        safe_subprocess_run([adb, "-s", dev, "shell", "input tap 360 500"], capture_output=True)
                        time.sleep(0.5)
                        safe_subprocess_run([adb, "-s", dev, "shell", "input text spsahnann@namecheap"], capture_output=True)
                        time.sleep(0.5)

                        # Enter password
                        safe_subprocess_run([adb, "-s", dev, "shell", "input tap 360 600"], capture_output=True)
                        time.sleep(0.5)
                        safe_subprocess_run([adb, "-s", dev, "shell", "input text s30NYSnlUE"], capture_output=True)
                        time.sleep(0.5)

                        # Save
                        safe_subprocess_run([adb, "-s", dev, "shell", "input keyevent 4"], capture_output=True)
                        time.sleep(2)
                    else:
                        self._vpn_signal.emit("log", f"Profile {label} already exists - using existing profile")

                    # Connect
                    self._vpn_signal.emit("log", "Connecting to VPN...")
                    safe_subprocess_run([adb, "-s", dev, "shell", "input tap 360 300"], capture_output=True)
                    time.sleep(5)

                    # Poll tun0 to verify connection
                    connected = False
                    for i in range(20):
                        tun = safe_subprocess_run([adb, "-s", dev, "shell", "ip addr show tun0"], capture_output=True)
                        if tun.stdout and "inet" in tun.stdout:
                            self._vpn_signal.emit("log", "VPN connected successfully - connection will persist")
                            connected = True
                            break
                        time.sleep(1)
                    
                    if connected:
                        self._vpn_signal.emit("connected", label)
                    else:
                        self._vpn_signal.emit("failed", "Connection failed - tun0 not detected")
            except Exception as e:
                self._vpn_signal.emit("failed", str(e))

        threading.Thread(target=_run, daemon=True).start()


    def _on_vpn_status(self, state, info):
        if hasattr(self, 'vpn_connect_btn'): self.vpn_connect_btn.setEnabled(True)
        if state == "log":
            self.add_activity(f"VPN: {info}")
            return
        elif state == "connected":
            self.vpn_status_dot.setStyleSheet("background: #4CAF50; border-radius: 5px;")
            self.vpn_status_val.setText(f"Connected: {info}")
            self.vpn_status_val.setStyleSheet("color: #4CAF50; font-size: 11px; background: transparent;")
            self.add_activity(f"VPN connected: {info}")
        else:
            self.vpn_status_dot.setStyleSheet("background: #f44336; border-radius: 5px;")
            self.vpn_status_val.setText("Failed")
            self.vpn_status_val.setStyleSheet("color: #f44336; font-size: 11px; background: transparent;")
            self.add_activity(f"VPN failed: {info}")
            QMessageBox.warning(self, "VPN Error", info)


    def _disconnect_vpn(self):
        adb = r"C:\Users\KLS COMPUTER\Desktop\FRT\platform-tools\adb.exe"
        devices = [cb.text() for cb in self.device_checkboxes if cb.isChecked()] if self.device_checkboxes else ["29ba10487d2b"]
        for dev in devices:
            safe_subprocess_run([adb, "-s", dev, "shell",
                "am start -n de.blinkt.openvpn/.api.DisconnectVPN"
            ], capture_output=True)
            safe_subprocess_run([adb, "-s", dev, "shell",
                "am broadcast -a de.blinkt.openvpn.DISCONNECT_VPN"
            ], capture_output=True)
        self.vpn_status_dot.setStyleSheet("background: #555555; border-radius: 5px;")
        self.vpn_status_val.setText("Disconnected")
        self.vpn_status_val.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
        self.add_activity("VPN disconnected on phone.")
    

    def refresh_devices(self):
        """Scan for connected Android devices using ADB - runs in background thread."""
        # Clear existing checkboxes
        for cb in self.device_checkboxes:
            cb.setParent(None)
            cb.deleteLater()
        self.device_checkboxes.clear()
        
        # Hide no devices label initially
        self.no_devices_label.setVisible(False)
        
        # Show loading indicator
        self.add_activity("Scanning for devices...")
        
        def _scan_devices_background():
            """Scan devices in background thread"""
            try:
                # Use the class adb_path
                adb_path = self.adb_path
                
                # Run adb devices command with proper encoding
                result = subprocess.run(
                    [adb_path, "devices"],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='ignore',
                    timeout=10
                )
                
                lines = result.stdout.strip().split('\n')
                
                devices = []
                for line in lines[1:]:  # Skip header line
                    line = line.strip()
                    if not line:
                        continue
                    # Split by whitespace and check for "device" status
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == 'device':
                        device_id = parts[0].strip()
                        devices.append(device_id)
                
                # Emit signal to update UI on main thread
                self._device_scan_signal.emit(devices)
                
            except subprocess.TimeoutExpired:
                self._device_scan_signal.emit([])  # Empty list on timeout
            except Exception as e:
                print(f"Error scanning devices: {e}")
                self._device_scan_signal.emit([])  # Empty list on error
        
        # Run scan in background thread
        import threading
        threading.Thread(target=_scan_devices_background, daemon=True).start()
    
    def _apply_device_list(self, devices):
        """Apply device list to UI - runs on main thread"""
        try:
            if devices:
                for device_id in devices:
                    cb = QCheckBox(device_id)
                    cb.setStyleSheet("""
                        QCheckBox {
                            color: #ffffff;
                            font-size: 12px;
                            padding: 8px;
                            background-color: #2d2d2d;
                            border-radius: 0px;
                        }
                        QCheckBox:hover {
                            background-color: #3d3d3d;
                        }
                        QCheckBox::indicator {
                            width: 16px;
                            height: 16px;
                        }
                        QCheckBox::indicator:unchecked {
                            border: 2px solid #555555;
                            background-color: #2d2d2d;
                            border-radius: 0px;
                        }
                        QCheckBox::indicator:checked {
                            border: 2px solid #4CAF50;
                            background-color: #4CAF50;
                            border-radius: 0px;
                        }
                    """)
                    cb.setChecked(True)  # Select all by default
                    # Keep _checked_device_ids in sync when user toggles a checkbox
                    def _on_toggle(checked, did=device_id):
                        ids = getattr(self, '_checked_device_ids', [])
                        if checked and did not in ids:
                            ids.append(did)
                        elif not checked and did in ids:
                            ids.remove(did)
                        self._checked_device_ids = ids
                    cb.toggled.connect(_on_toggle)
                    self.device_checkboxes.append(cb)
                    self.device_list_layout.addWidget(cb)
                
                # Update legacy device_input with first device for compatibility
                self.device_input.setText(devices[0])
                self.add_activity(f"✓ Found {len(devices)} device(s)")
                self.devices_loaded = True
                # Cache device IDs as plain list so they survive checkbox deleteLater() cycles
                self._checked_device_ids = list(devices)
                # Re-apply green to account table now that devices are confirmed loaded
                self.load_main_account_tab()
                # Also refresh all other tab device lists
                if hasattr(self, 'login_device_select'):
                    self.load_login_devices()
                if hasattr(self, 'batch_device_cards'):
                    self.refresh_batch_devices()
                if hasattr(self, 'auto_reg_device_select'):
                    self.load_auto_reg_devices()
                if hasattr(self, 'seed_device_table'):
                    self._load_seeding_devices()
                
                # Update dashboard device count label and cache so monitor timer stays in sync
                if hasattr(self, 'device_count_label'):
                    self.device_count_label.setText(f"{len(devices)} detected")
                self.device_count_cache = len(devices)
                self.device_count_last_check = time.time()
                # Update device count label in Panel 1 — show selected count, not total
                if hasattr(self, 'panel1_device_count_label'):
                    selected_count = len(self._saved_selected_device_ids) if hasattr(self, '_saved_selected_device_ids') and self._saved_selected_device_ids else len(devices)
                    self.panel1_device_count_label.setText(f"{selected_count} device(s) connected")
                    self.panel1_device_count_label.setStyleSheet("color: #4CAF50; padding: 10px; margin-top: 10px;")
                # Update device table in Accounts-only tab if open
                if hasattr(self, '_accounts_only_device_table'):
                    try:
                        self._load_devices_only_table(self._accounts_only_device_table)
                        if hasattr(self, '_devices_count_label'):
                            self._devices_count_label.setText(f"{self._accounts_only_device_table.rowCount()} devices")
                    except RuntimeError:
                        pass
            else:
                self.no_devices_label.setText("No devices found. Make sure USB debugging is enabled.")
                self.no_devices_label.setVisible(True)
                self.add_activity("No devices found")
                
                # Update device count label
                if hasattr(self, 'panel1_device_count_label'):
                    self.panel1_device_count_label.setText("No devices connected")
                    self.panel1_device_count_label.setStyleSheet("color: #666666; padding: 10px; margin-top: 10px;")
        except Exception as e:
            print(f"Error applying device list: {e}")
            import traceback
            traceback.print_exc()
    

    def test_device_changer(self):
        """Test device changer functionality and show results."""
        try:
            # Get selected devices
            selected_devices = self.get_selected_devices()
            if not selected_devices:
                QMessageBox.warning(self, "Error", "No devices selected! Please select a device first.")
                return
            
            device_id = selected_devices[0]
            
            # Generate fake device info
            fake_device_info = self.generate_fake_device_info()
            
            # Show dialog with generated info
            dialog = QDialog(self)
            dialog.setWindowTitle(_T("dlg_device_test"))
            dialog.setFixedSize(600, 500)
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #1e1e1e;
                    color: #ffffff;
                }
                QTextEdit {
                    background-color: #2d2d2d;
                    border: 1px solid #3d3d3d;
                    border-radius: 0px;
                    color: #ffffff;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 11px;
                    padding: 10px;
                }
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    border: none;
                    border-radius: 0px;
                    padding: 10px 20px;
                    font-weight: 600;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #F57C00;
                }
                QLabel {
                    color: #e0e0e0;
                    font-size: 13px;
                }
            """)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(15)
            layout.setContentsMargins(20, 20, 20, 20)
            
            # Title
            title = QLabel("🔧 Device Changer Test Results")
            title.setStyleSheet("color: #FF9800; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(title)
            
            # Device info display
            info_text = QTextEdit()
            info_text.setReadOnly(True)
            
            # Get current device info for comparison
            current_info = self._get_current_device_info(device_id)
            
            info_content = "🔍 CURRENT DEVICE INFORMATION:\n"
            info_content += "=" * 50 + "\n"
            for key, value in current_info.items():
                info_content += f"{key.replace('_', ' ').title()}: {value}\n"
            
            info_content += "\n🎭 GENERATED FAKE DEVICE INFORMATION:\n"
            info_content += "=" * 50 + "\n"
            
            for key, value in fake_device_info.items():
                info_content += f"{key.replace('_', ' ').title()}: {value}\n"
            
            info_content += "\n🛡️ ANTI-DETECTION FEATURES:\n"
            info_content += "=" * 50 + "\n"
            info_content += f"✅ Realistic Device Model: {fake_device_info.get('manufacturer', 'N/A')} {fake_device_info.get('model', 'N/A')}\n"
            info_content += f"✅ Valid Android Version: {fake_device_info.get('android_version', 'N/A')} (SDK {fake_device_info.get('android_sdk', 'N/A')})\n"
            info_content += f"✅ Authentic Build Fingerprint: Generated\n"
            info_content += f"✅ Unique Android ID: {fake_device_info.get('android_id', 'N/A')}\n"
            info_content += f"✅ Realistic IMEI: {fake_device_info.get('imei', 'N/A')}\n"
            info_content += f"✅ Valid MAC Address: {fake_device_info.get('mac_address', 'N/A')}\n"
            info_content += f"✅ Hardware Specs: {fake_device_info.get('total_ram_mb', 'N/A')}MB RAM, {fake_device_info.get('storage_gb', 'N/A')}GB Storage\n"
            
            # Check root status
            info_content += "\n🔐 ROOT STATUS CHECK:\n"
            info_content += "=" * 50 + "\n"
            
            import subprocess
            try:
                result = safe_subprocess_run([
                    self.adb_path, '-s', device_id, 'shell', 'su -c "echo ROOT_ACCESS_OK"'
                ], capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0 and 'ROOT_ACCESS_OK' in result.stdout:
                    info_content += "✅ ROOT ACCESS: Available - Full device spoofing possible\n"
                    info_content += "   • Can modify system properties\n"
                    info_content += "   • Can change Android ID\n"
                    info_content += "   • Can modify build.prop\n"
                    info_content += "   • Can change MAC address (device dependent)\n"
                else:
                    info_content += "⚠️  ROOT ACCESS: Not available - Limited spoofing mode\n"
                    info_content += "   • App-level property changes only\n"
                    info_content += "   • Facebook Lite app data will be cleared\n"
                    info_content += "   • Still effective for most detection methods\n"
            except:
                info_content += "❌ ROOT ACCESS: Could not determine\n"
            
            info_content += "\n📱 DEVICE COMPATIBILITY:\n"
            info_content += "=" * 50 + "\n"
            info_content += f"Device ID: {device_id}\n"
            info_content += f"Target Device: {current_info.get('manufacturer', 'Unknown')} {current_info.get('model', 'Unknown')}\n"
            info_content += f"Android Version: {current_info.get('android_version', 'Unknown')}\n"
            info_content += "Status: ✅ Compatible with Device Changer\n"
            
            info_text.setPlainText(info_content)
            layout.addWidget(info_text)
            
            # Buttons
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            
            apply_btn = QPushButton("Apply Changes Now")
            apply_btn.clicked.connect(lambda: self._apply_test_changes(device_id, fake_device_info, dialog))
            btn_layout.addWidget(apply_btn)
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            btn_layout.addWidget(close_btn)
            
            layout.addLayout(btn_layout)
            
            dialog.exec()
            
        except Exception as e:
            self.add_activity(f"❌ Device Changer test failed: {e}")
            QMessageBox.critical(self, "Error", f"Device Changer test failed:\n{e}")
    

    def open_device_changer_advanced_settings(self):
        """Open advanced device changer settings dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_device_adv"))
        dialog.setFixedSize(500, 600)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 12px;
            }
            QCheckBox {
                color: #b0b0b0;
                font-size: 11px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #555555;
                background-color: #2d2d2d;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4CAF50;
                background-color: #4CAF50;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton#closeBtn {
                background-color: #555555;
            }
            QPushButton#closeBtn:hover {
                background-color: #666666;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Device Changer - Advanced Settings")
        title.setStyleSheet("color: #FF9800; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel("Select which device identifiers to change for anti-detection:")
        desc.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 10px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Checkboxes section
        options_label = QLabel("What to Change:")
        options_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(options_label)
        
        # Android ID
        android_id_cb = QCheckBox("✓ Android ID")
        android_id_cb.setChecked(self.change_android_id_checkbox.isChecked())
        layout.addWidget(android_id_cb)
        
        android_id_desc = QLabel("   Unique identifier for the device")
        android_id_desc.setStyleSheet("color: #666666; font-size: 10px; margin-left: 20px;")
        layout.addWidget(android_id_desc)
        
        # Device Model
        device_model_cb = QCheckBox("✓ Device Model & Manufacturer")
        device_model_cb.setChecked(self.change_device_model_checkbox.isChecked())
        layout.addWidget(device_model_cb)
        
        device_model_desc = QLabel("   Brand and model name (e.g., Samsung Galaxy S21)")
        device_model_desc.setStyleSheet("color: #666666; font-size: 10px; margin-left: 20px;")
        layout.addWidget(device_model_desc)
        
        # Build Fingerprint
        build_fp_cb = QCheckBox("✓ Build Fingerprint")
        build_fp_cb.setChecked(self.change_build_fingerprint_checkbox.isChecked())
        layout.addWidget(build_fp_cb)
        
        build_fp_desc = QLabel("   System build signature and version info")
        build_fp_desc.setStyleSheet("color: #666666; font-size: 10px; margin-left: 20px;")
        layout.addWidget(build_fp_desc)
        
        # Serial Number
        serial_cb = QCheckBox("✓ Serial Number")
        serial_cb.setChecked(self.change_serial_checkbox.isChecked())
        layout.addWidget(serial_cb)
        
        serial_desc = QLabel("   Hardware serial number")
        serial_desc.setStyleSheet("color: #666666; font-size: 10px; margin-left: 20px;")
        layout.addWidget(serial_desc)
        
        # MAC Address
        mac_cb = QCheckBox("✓ MAC Address (WiFi)")
        mac_cb.setChecked(self.change_mac_address_checkbox.isChecked())
        layout.addWidget(mac_cb)
        
        mac_desc = QLabel("   Network adapter hardware address")
        mac_desc.setStyleSheet("color: #666666; font-size: 10px; margin-left: 20px;")
        layout.addWidget(mac_desc)
        
        layout.addStretch()
        
        # Info box
        info_box = QLabel("All changes are randomized per account and saved in backup files. Root access provides better spoofing capabilities.")
        info_box.setStyleSheet("""
            color: #888888;
            font-size: 10px;
            padding: 10px;
            background-color: rgba(255, 152, 0, 0.1);
            border-radius: 6px;
            border: 1px solid #FF9800;
        """)
        info_box.setWordWrap(True)
        layout.addWidget(info_box)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton(" Save Settings")
        save_btn.setIcon(qta.icon('fa5s.save', color='#ffffff'))
        save_btn.clicked.connect(lambda: self.save_advanced_settings(
            android_id_cb.isChecked(),
            device_model_cb.isChecked(),
            build_fp_cb.isChecked(),
            serial_cb.isChecked(),
            mac_cb.isChecked(),
            dialog
        ))
        btn_layout.addWidget(save_btn)
        
        close_btn = QPushButton("Cancel")
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()
    

    def save_advanced_settings(self, android_id, device_model, build_fp, serial, mac, dialog):
        """Save advanced device changer settings."""
        self.change_android_id_checkbox.setChecked(android_id)
        self.change_device_model_checkbox.setChecked(device_model)
        self.change_build_fingerprint_checkbox.setChecked(build_fp)
        self.change_serial_checkbox.setChecked(serial)
        self.change_mac_address_checkbox.setChecked(mac)
        
        self.add_activity("✓ Advanced device changer settings saved")
        QMessageBox.information(dialog, "Success", "Advanced settings saved successfully!")
        dialog.accept()
    

    def open_vpn_advanced_settings(self):
        """Open VPN advanced settings dialog with 3 horizontal panels."""
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_vpn_settings"))
        dialog.setFixedSize(800, 560)
        dialog.setStyleSheet("""
            QDialog { background: #1e1e1e; }
            QLabel { color: #cccccc; font-size: 12px; background: transparent; }
            QComboBox {
                background: #252526; border: 1px solid #3d3d3d; border-radius: 4px;
                padding: 0 10px; color: #cccccc; font-size: 12px; height: 36px;
            }
            QComboBox:hover { border-color: #4CAF50; }
            QComboBox::drop-down { border: none; width: 22px; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #888888; margin-right: 8px; }
            QComboBox QAbstractItemView { background: #252526; border: 1px solid #3d3d3d; color: #cccccc; selection-background-color: #2a4a2a; }
            QLineEdit {
                background: #252526; border: 1px solid #3d3d3d; border-radius: 4px;
                padding: 0 10px; color: #cccccc; font-size: 12px; height: 36px;
            }
            QLineEdit:focus { border-color: #4CAF50; }
        """)

        root = QVBoxLayout(dialog)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame(); hdr.setObjectName("vpnHdr")
        hdr.setFixedHeight(60)
        hdr.setStyleSheet("QFrame#vpnHdr { background: #252526; border: none; border-bottom: 1px solid #3d3d3d; }")
        hdr_l = QHBoxLayout(hdr); hdr_l.setContentsMargins(24, 0, 24, 0); hdr_l.setSpacing(12)
        ico = QLabel(); ico.setPixmap(qta.icon('fa5s.shield-alt', color='#4CAF50').pixmap(18, 18)); ico.setStyleSheet("background: transparent;")
        hdr_l.addWidget(ico)
        ttl = QLabel("VPN Configuration"); ttl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; background: transparent;")
        hdr_l.addWidget(ttl); hdr_l.addStretch()
        root.addWidget(hdr)

        # 3 Horizontal Panels
        panels_row = QHBoxLayout()
        panels_row.setSpacing(1)
        panels_row.setContentsMargins(0, 0, 0, 0)

        _fh  = 38
        _btn_green = "QPushButton { background: #4CAF50; color: #fff; border: none; border-radius: 4px; font-size: 13px; font-weight: 600; padding: 8px 16px; } QPushButton:hover { background: #45a049; }"
        _btn_ghost = "QPushButton { background: transparent; color: #cccccc; border: 1px solid #3d3d3d; border-radius: 4px; font-size: 12px; padding: 8px 16px; } QPushButton:hover { border-color: #4CAF50; color: #ffffff; background: #252526; }"

        def _create_panel(num, title, is_last=False):
            panel = QFrame()
            border_style = "border: none;" if is_last else "border-right: 1px solid #2a2a2a;"
            panel.setStyleSheet(f"QFrame {{ background: #1e1e1e; {border_style} }}")
            panel_l = QVBoxLayout(panel)
            panel_l.setContentsMargins(28, 28, 28, 28)
            panel_l.setSpacing(16)
            
            # Panel header with badge
            badge_row = QHBoxLayout(); badge_row.setSpacing(12)
            badge = QLabel(str(num)); badge.setFixedSize(28, 28)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet("background: #4CAF50; color: #fff; border-radius: 14px; font-size: 13px; font-weight: bold;")
            badge_row.addWidget(badge)
            t = QLabel(title); t.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600; background: transparent;")
            badge_row.addWidget(t); badge_row.addStretch()
            panel_l.addLayout(badge_row)
            
            # Separator
            sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("background: #3d3d3d; border: none; max-height: 1px; margin: 4px 0;")
            panel_l.addWidget(sep)
            
            return panel, panel_l

        vpn_dir_path = os.path.join(_PROJECT_ROOT, "vpn")
        vpn_count = len([f for f in os.listdir(vpn_dir_path) if f.endswith(".ovpn")]) if os.path.exists(vpn_dir_path) else 0

        # ── PANEL 1: Push Files ────────────────────────────────
        p1, p1l = _create_panel(1, "Push Files")

        # Folder path input row
        folder_row = QHBoxLayout(); folder_row.setSpacing(8)
        self.vpn_folder_input = QLineEdit()
        self.vpn_folder_input.setFixedHeight(_fh)
        self.vpn_folder_input.setPlaceholderText("VPN folder path...")
        self.vpn_folder_input.setText(vpn_dir_path)
        folder_row.addWidget(self.vpn_folder_input, 1)
        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(90)
        browse_btn.setFixedHeight(_fh)
        browse_btn.setStyleSheet(_btn_ghost)
        def _browse_vpn_folder():
            from PyQt6.QtWidgets import QFileDialog
            folder = QFileDialog.getExistingDirectory(dialog, "Select VPN Folder", self.vpn_folder_input.text())
            if folder:
                self.vpn_folder_input.setText(folder)
                count = len([f for f in os.listdir(folder) if f.endswith(".ovpn")])
                count_lbl1.setText(f"{count} .ovpn files")
                push_btn.setText(f"Push {count} Files")
        browse_btn.clicked.connect(_browse_vpn_folder)
        folder_row.addWidget(browse_btn)
        p1l.addLayout(folder_row)

        count_lbl1 = QLabel(f"{vpn_count} .ovpn files")
        count_lbl1.setStyleSheet("color: #4CAF50; font-size: 12px; font-weight: 600; background: transparent; margin-top: 4px;")
        p1l.addWidget(count_lbl1)
        
        dest_lbl = QLabel("→ /data/local/tmp/vpn/")
        dest_lbl.setStyleSheet("color: #888888; font-size: 11px; background: transparent;")
        p1l.addWidget(dest_lbl)
        
        p1l.addStretch()
        
        push_btn = QPushButton(f"Push {vpn_count} Files")
        push_btn.setIcon(qta.icon('fa5s.upload', color='#ffffff'))
        push_btn.setFixedHeight(42); push_btn.setStyleSheet(_btn_green)
        push_btn.setDefault(False); push_btn.setAutoDefault(False)
        push_btn.clicked.connect(self._push_all_vpn_to_phone)
        p1l.addWidget(push_btn)
        
        panels_row.addWidget(p1, 1)

        # ── PANEL 2: Import Profiles ───────────────
        p2, p2l = _create_panel(2, "Import Profiles")

        # ── Group 1: UI Automation ──
        grp1_lbl = QLabel("UI AUTOMATION")
        grp1_lbl.setStyleSheet("color: #555555; font-size: 10px; font-weight: 700; letter-spacing: 1px; background: transparent;")
        p2l.addWidget(grp1_lbl)

        import_btn = QPushButton(f"  Import All  ({vpn_count} files)")
        import_btn.setIcon(qta.icon('fa5s.file-import', color='#ffffff'))
        import_btn.setFixedHeight(40); import_btn.setStyleSheet(_btn_green)
        import_btn.setDefault(False); import_btn.setAutoDefault(False)
        import_btn.setToolTip("Import all .ovpn files from the VPN folder (~6s per file)")
        import_btn.clicked.connect(self._push_vpn_file)
        p2l.addWidget(import_btn)

        multi_import_btn = QPushButton("  Import Selected Files")
        multi_import_btn.setIcon(qta.icon('fa5s.folder-open', color='#4CAF50'))
        multi_import_btn.setFixedHeight(40); multi_import_btn.setStyleSheet(_btn_ghost)
        multi_import_btn.setDefault(False); multi_import_btn.setAutoDefault(False)
        multi_import_btn.setToolTip("Pick specific .ovpn files to import")
        multi_import_btn.clicked.connect(self._import_multiple_vpn_files)
        p2l.addWidget(multi_import_btn)

        # Divider
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background: #2a2a2a; border: none; max-height: 1px; margin: 6px 0;")
        p2l.addWidget(div)

        # ── Group 2: Backup / Restore ──
        grp2_lbl = QLabel("BACKUP & RESTORE")
        grp2_lbl.setStyleSheet("color: #555555; font-size: 10px; font-weight: 700; letter-spacing: 1px; background: transparent;")
        p2l.addWidget(grp2_lbl)

        bk_row = QHBoxLayout(); bk_row.setSpacing(8)
        backup_btn = QPushButton("Backup")
        backup_btn.setIcon(qta.icon('fa5s.download', color='#ffffff'))
        backup_btn.setFixedHeight(40); backup_btn.setStyleSheet(_btn_green)
        backup_btn.setToolTip("Backup current OpenVPN profiles")
        backup_btn.clicked.connect(self._backup_vpn_profiles)
        bk_row.addWidget(backup_btn, 1)

        restore_btn = QPushButton("Restore")
        restore_btn.setIcon(qta.icon('fa5s.upload', color='#ffffff'))
        restore_btn.setFixedHeight(40); restore_btn.setStyleSheet(_btn_green)
        restore_btn.setToolTip("Restore profiles from backup")
        restore_btn.clicked.connect(self._restore_vpn_profiles)
        bk_row.addWidget(restore_btn, 1)
        p2l.addLayout(bk_row)

        p2l.addStretch()
        panels_row.addWidget(p2, 1)

        root.addLayout(panels_row, 1)

        # Footer — Save Settings | Connect VPN | Cancel
        ftr = QFrame(); ftr.setObjectName("vpnFtr")
        ftr.setFixedHeight(64)
        ftr.setStyleSheet("QFrame#vpnFtr { background: #252526; border: none; border-top: 1px solid #3d3d3d; }")
        ftr_l = QHBoxLayout(ftr); ftr_l.setContentsMargins(24, 0, 24, 0); ftr_l.setSpacing(10)
        ftr_l.addStretch()

        save_btn = QPushButton("Save Settings")
        save_btn.setIcon(qta.icon('fa5s.save', color='#ffffff'))
        save_btn.setFixedSize(140, 38)
        save_btn.setStyleSheet(_btn_green)
        save_btn.setDefault(False); save_btn.setAutoDefault(False)
        save_btn.clicked.connect(lambda: self._save_vpn_settings(dialog))
        ftr_l.addWidget(save_btn)

        connect_btn = QPushButton("Connect VPN")
        connect_btn.setIcon(qta.icon('fa5s.plug', color='#ffffff'))
        connect_btn.setFixedSize(140, 38)
        connect_btn.setStyleSheet(_btn_green)
        connect_btn.setDefault(False); connect_btn.setAutoDefault(False)
        def _on_connect():
            self._connect_vpn()
            dialog.accept()
        connect_btn.clicked.connect(_on_connect)
        ftr_l.addWidget(connect_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(90, 38)
        cancel_btn.setStyleSheet(_btn_ghost)
        cancel_btn.setDefault(False); cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(dialog.reject)
        ftr_l.addWidget(cancel_btn)

        root.addWidget(ftr)

        self._load_vpn_dialog_settings()
        dialog.exec()
    

    def _populate_vpn_servers(self):
        """Populate VPN server dropdown from vpn/ folder."""
        vpn_dir = os.path.join(_PROJECT_ROOT, "vpn")
        if not os.path.exists(vpn_dir):
            return

        files = [f for f in os.listdir(vpn_dir) if f.endswith(".ovpn")]
        for f in sorted(files):
            # Format: NCVPN-US-Los Angeles-TCP.ovpn
            # Strip prefix NCVPN- and suffix -TCP
            name = f.replace(".ovpn", "")
            if name.startswith("NCVPN-"):
                name = name[6:]          # "US-Los Angeles-TCP"
            if name.endswith("-TCP"):
                name = name[:-4]         # "US-Los Angeles"
            elif name.endswith("-UDP"):
                name = name[:-4]
            # Split only on first dash to get country code
            idx = name.index("-") if "-" in name else -1
            if idx > 0:
                country = name[:idx]     # "US"
                city = name[idx+1:]      # "Los Angeles"
                label = f"{country} - {city}"
            else:
                label = name
            self.vpn_server_combo.addItem(label, f)
    

    def _load_vpn_dialog_settings(self):
        """No-op — dialog widgets removed."""
        pass
    

    def _save_vpn_settings(self, dialog):
        """Save VPN settings from dialog."""
        self.save_settings()
        self.add_activity("✓ VPN settings saved")
        QMessageBox.information(dialog, "Success", "VPN settings saved successfully!")
        dialog.accept()
    

    def open_device_settings_dialog(self):
        """Open device settings dialog with a table view."""
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_device_settings"))
        dialog.setFixedSize(980, 520)
        dialog.setStyleSheet("""
            QDialog { background: #1e1e1e; }
            QLabel { color: #cccccc; font-size: 12px; background: transparent; }
            QTableWidget {
                background: #1e1e1e; border: none; gridline-color: #2a2a2a;
                color: #cccccc; font-size: 12px; outline: none;
            }
            QHeaderView::section {
                background: #252526; color: #888888; font-size: 10px; font-weight: 700;
                letter-spacing: 0.8px; padding: 6px 10px;
                border: none; border-bottom: 1px solid #3d3d3d; border-right: 1px solid #2a2a2a;
            }
            QScrollBar:vertical { background: #1e1e1e; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #3d3d3d; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #4CAF50; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        root = QVBoxLayout(dialog)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Header ──
        hdr = QFrame(); hdr.setObjectName("dHdr")
        hdr.setFixedHeight(56)
        hdr.setStyleSheet("QFrame#dHdr { background: #252526; border-bottom: 1px solid #2a2a2a; }")
        hdr_l = QHBoxLayout(hdr); hdr_l.setContentsMargins(20, 0, 20, 0); hdr_l.setSpacing(10)
        ico = QLabel(); ico.setPixmap(qta.icon('fa5s.mobile-alt', color='#4CAF50').pixmap(16, 16)); ico.setStyleSheet("background:transparent;")
        hdr_l.addWidget(ico)
        ttl = QLabel("Device & Connection Settings")
        ttl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold; background: transparent;")
        hdr_l.addWidget(ttl); hdr_l.addStretch()
        root.addWidget(hdr)

        # ── Toolbar ──
        tb = QWidget(); tb.setStyleSheet("background: #1e1e1e;")
        tb_l = QHBoxLayout(tb); tb_l.setContentsMargins(20, 12, 20, 8); tb_l.setSpacing(8)

        sec_lbl = QLabel("CONNECTED DEVICES")
        sec_lbl.setStyleSheet("color: #555555; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
        tb_l.addWidget(sec_lbl)
        tb_l.addStretch()

        sel_all_btn = QPushButton("Select All")
        sel_all_btn.setFixedHeight(30)
        sel_all_btn.setStyleSheet("QPushButton { background: transparent; color: #888888; border: 1px solid #3d3d3d; border-radius: 4px; font-size: 11px; padding: 0 10px; } QPushButton:hover { border-color: #4CAF50; color: #ffffff; }")
        tb_l.addWidget(sel_all_btn)

        desel_all_btn = QPushButton("Deselect All")
        desel_all_btn.setFixedHeight(30)
        desel_all_btn.setStyleSheet("QPushButton { background: transparent; color: #888888; border: 1px solid #3d3d3d; border-radius: 4px; font-size: 11px; padding: 0 10px; } QPushButton:hover { border-color: #f44336; color: #ffffff; }")
        tb_l.addWidget(desel_all_btn)

        refresh_btn = QPushButton("  Refresh")
        refresh_btn.setIcon(qta.icon('fa5s.sync-alt', color='#ffffff'))
        refresh_btn.setFixedHeight(30)
        refresh_btn.setStyleSheet("QPushButton { background: #4CAF50; color: #fff; border: none; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 0 14px; } QPushButton:hover { background: #45a049; }")
        tb_l.addWidget(refresh_btn)
        root.addWidget(tb)

        # ── Table ──
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels(["", "#", "DEVICE ID", "BRAND", "MODEL", "ANDROID", "BATTERY", "RESOLUTION", "ACCOUNT"])
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 44)   # checkbox
        table.setColumnWidth(1, 32)   # #
        table.setColumnWidth(2, 170)  # device id
        table.setColumnWidth(3, 90)   # brand
        table.setColumnWidth(4, 100)  # model
        table.setColumnWidth(5, 72)   # android
        table.setColumnWidth(6, 72)   # battery
        table.setColumnWidth(7, 100)  # resolution
        table.verticalHeader().setDefaultSectionSize(44)

        _row_checkboxes = []

        # Wrap table
        tbl_wrap = QWidget(); tbl_wrap.setStyleSheet("background: #1e1e1e;")
        tbl_wrap_l = QVBoxLayout(tbl_wrap); tbl_wrap_l.setContentsMargins(20, 0, 20, 0)
        tbl_wrap_l.addWidget(table)
        root.addWidget(tbl_wrap, 1)

        # ── Footer ──
        ftr = QFrame(); ftr.setObjectName("dFtr")
        ftr.setFixedHeight(60)
        ftr.setStyleSheet("QFrame#dFtr { background: #252526; border-top: 1px solid #2a2a2a; }")
        ftr_l = QHBoxLayout(ftr); ftr_l.setContentsMargins(20, 0, 20, 0); ftr_l.setSpacing(10)
        count_lbl = QLabel("0 device(s) selected")
        count_lbl.setStyleSheet("color: #555555; font-size: 11px;")
        ftr_l.addWidget(count_lbl)
        ftr_l.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(90, 36)
        cancel_btn.setStyleSheet("QPushButton { background: #2d2d2d; color: #aaaaaa; border: 1px solid #3d3d3d; border-radius: 5px; font-size: 12px; } QPushButton:hover { border-color: #4CAF50; color: #fff; }")
        cancel_btn.clicked.connect(dialog.reject)
        ftr_l.addWidget(cancel_btn)
        save_btn = QPushButton("  Save Selection")
        save_btn.setIcon(qta.icon('fa5s.save', color='#ffffff'))
        save_btn.setFixedSize(140, 36)
        save_btn.setStyleSheet("QPushButton { background: #4CAF50; color: #fff; border: none; border-radius: 5px; font-size: 12px; font-weight: bold; } QPushButton:hover { background: #45a049; }")
        ftr_l.addWidget(save_btn)
        root.addWidget(ftr)

        def _set_row_bg(row, checked):
            bg = QColor("#1a2e1a") if checked else QColor("#1e1e1e")
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item:
                    item.setData(Qt.ItemDataRole.BackgroundRole, bg)
            w = table.cellWidget(row, 0)
            if w:
                w.setStyleSheet(f"background: {'#1a2e1a' if checked else 'transparent'};")

        def _on_selection_changed():
            n = sum(1 for cb in _row_checkboxes if cb.isChecked())
            count_lbl.setText(f"{n} of {len(_row_checkboxes)} device(s) selected")
            # update row backgrounds
            for r, cb in enumerate(_row_checkboxes):
                _set_row_bg(r, cb.isChecked())

        # Use module-level _DeviceWorker (pyqtSignal requires class-level definition)
        _worker = [None]  # keep reference to avoid GC
        _device_info_cache = {}  # dev_id -> display name from worker results

        def _fill_table(rows):
            try:
                # Cache device info for use in _save
                for dev_id, brand, model, android, battery, resolution, account_uid, order_num in rows:
                    label = f"{dev_id} ({model})" if model else dev_id
                    _device_info_cache[dev_id] = label
                table.clearSpans()
                table.setRowCount(0)
                _row_checkboxes.clear()

                def _item(text, color="#cccccc", align=None):
                    it = QTableWidgetItem(text if text else "—")
                    it.setForeground(QColor(color))
                    if align:
                        it.setTextAlignment(align)
                    return it

                selected_ids = set()
                # Primary: use persisted selection from last save
                if hasattr(self, '_saved_selected_device_ids') and self._saved_selected_device_ids:
                    selected_ids = self._saved_selected_device_ids
                # Fallback: read from live device_checkboxes
                elif self.device_checkboxes:
                    selected_ids = {cb.text() for cb in self.device_checkboxes if cb.isChecked()}
                for idx, (dev_id, brand, model, android, battery, resolution, account_uid, order_num) in enumerate(rows):
                    is_checked = (dev_id in selected_ids) if selected_ids else True
                    table.insertRow(idx)

                    cb_widget = QWidget(); cb_widget.setStyleSheet("background: transparent;")
                    cb_lay = QHBoxLayout(cb_widget); cb_lay.setContentsMargins(0,0,0,0)
                    cb_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    cb = QCheckBox(); cb.setChecked(is_checked); cb.setProperty("device_id", dev_id)
                    cb.setStyleSheet("""
                        QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid #3d3d3d; border-radius: 3px; background: #252526; }
                        QCheckBox::indicator:checked { background: #4CAF50; border-color: #4CAF50; }
                        QCheckBox::indicator:hover { border-color: #4CAF50; }
                    """)
                    cb.stateChanged.connect(_on_selection_changed)
                    cb_lay.addWidget(cb)
                    table.setCellWidget(idx, 0, cb_widget)
                    table.setRowHeight(idx, 44)
                    _row_checkboxes.append(cb)

                    table.setItem(idx, 1, _item(str(order_num), "#4CAF50", Qt.AlignmentFlag.AlignCenter))
                    table.setItem(idx, 2, _item(dev_id, "#4CAF50"))
                    table.setItem(idx, 3, _item(brand.capitalize() if brand else "—", "#cccccc"))
                    table.setItem(idx, 4, _item(model, "#cccccc"))
                    table.setItem(idx, 5, _item(android, "#2196F3"))

                    bat_item = QTableWidgetItem(battery if battery else "—")
                    if battery:
                        pct = int(battery.replace('%', ''))
                        bat_item.setForeground(QColor("#4CAF50" if pct > 50 else "#FF9800" if pct > 20 else "#f44336"))
                    else:
                        bat_item.setForeground(QColor("#555555"))
                    table.setItem(idx, 6, bat_item)
                    table.setItem(idx, 7, _item(resolution, "#888888"))
                    table.setItem(idx, 8, _item(account_uid, "#FFD700" if account_uid != "—" else "#555555"))
                    _set_row_bg(idx, is_checked)

                if table.rowCount() == 0:
                    table.insertRow(0)
                    empty = QTableWidgetItem("No devices detected — click Refresh")
                    empty.setForeground(QColor("#555555"))
                    empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(0, 0, empty)
                    table.setSpan(0, 0, 1, 9)

                refresh_btn.setEnabled(True)
                _on_selection_changed()
                table.scrollToTop()
                table.repaint()
            except RuntimeError:
                pass  # dialog closed before worker finished

        # Wire row click + drag to toggle checkboxes
        _drag_state = [None]  # None | True (checking) | False (unchecking)

        def _row_from_pos(pos):
            item = table.itemAt(pos)
            if item:
                return item.row()
            # also check via rowAt
            row = table.rowAt(pos.y())
            return row if row >= 0 else None

        def _toggle_row(row, state=None):
            if row is None or row >= len(_row_checkboxes):
                return
            cb = _row_checkboxes[row]
            cb.setChecked(state if state is not None else not cb.isChecked())

        from PyQt6.QtCore import QEvent
        class _DragFilter(QObject):
            def eventFilter(self_, obj, event):
                if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                    row = _row_from_pos(event.pos())
                    if row is not None and row < len(_row_checkboxes):
                        new_state = not _row_checkboxes[row].isChecked()
                        _drag_state[0] = new_state
                        _toggle_row(row, new_state)
                    return False
                elif event.type() == QEvent.Type.MouseMove and event.buttons() & Qt.MouseButton.LeftButton:
                    if _drag_state[0] is not None:
                        row = _row_from_pos(event.pos())
                        _toggle_row(row, _drag_state[0])
                    return False
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    _drag_state[0] = None
                    return False
                return False

        _drag_filter = _DragFilter(table.viewport())
        table.viewport().installEventFilter(_drag_filter)
        table.viewport().setMouseTracking(True)

        def _populate_table():
            table.clearSpans()
            table.setRowCount(0)  # clears all cell widgets too
            table.setRowCount(1)
            _row_checkboxes.clear()
            loading = QTableWidgetItem("  Scanning devices...")
            loading.setForeground(QColor("#555555"))
            loading.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(0, 0, loading)
            table.setSpan(0, 0, 1, 9)
            refresh_btn.setEnabled(False)

            from src.workers.device_worker import DeviceWorker as _DeviceWorker
            worker = _DeviceWorker(self.adb_path)
            worker.done.connect(_fill_table)
            _worker[0] = worker  # prevent GC
            worker.start()

        # Toolbar wiring
        def _select_all():
            for cb in _row_checkboxes: cb.setChecked(True)
        def _deselect_all():
            for cb in _row_checkboxes: cb.setChecked(False)
        def _refresh():
            _populate_table()

        sel_all_btn.clicked.connect(_select_all)
        desel_all_btn.clicked.connect(_deselect_all)
        refresh_btn.clicked.connect(_refresh)

        def _save():
            checked_ids = {cb.property("device_id") for cb in _row_checkboxes if cb.isChecked()}

            # Rebuild device_checkboxes from scratch based on dialog selection
            for cb in self.device_checkboxes:
                cb.setParent(None)
                cb.deleteLater()
            self.device_checkboxes.clear()

            for dev_id in checked_ids:
                cb = QCheckBox(dev_id)
                cb.setChecked(True)
                self.device_checkboxes.append(cb)
                self.device_list_layout.addWidget(cb)

            # Update legacy device_input
            if checked_ids:
                self.device_input.setText(next(iter(checked_ids)))
                self.devices_loaded = True
                if hasattr(self, 'device_count_label'):
                    self.device_count_label.setText(f"{len(checked_ids)} detected")
                self.device_count_cache = len(checked_ids)
                self.device_count_last_check = time.time()
                if hasattr(self, 'panel1_device_count_label'):
                    self.panel1_device_count_label.setText(f"{len(checked_ids)} device(s) connected")
                    self.panel1_device_count_label.setStyleSheet("color: #4CAF50; padding: 10px; margin-top: 10px;")

            self.add_activity(f"Device selection saved: {len(checked_ids)} device(s) active")
            self._saved_selected_device_ids = set(checked_ids)
            self.save_settings()
            dialog.accept()
            # Write device assignments to cache then reload table
            if checked_ids and self.account_table.rowCount() > 0:
                # preserve ADB order from cache, not random set order
                devices_list = [d for d in _device_info_cache.keys() if d in checked_ids]
                for idx in range(self.account_table.rowCount()):
                    dev_id = devices_list[idx % len(devices_list)]
                    display = _device_info_cache.get(dev_id, dev_id)
                    uid_item = self.account_table.item(idx, 1)
                    if uid_item:
                        self._update_account_device_in_backup(uid_item.text(), display, "Device Assigned")
                self.devices_loaded = True
                self.add_activity(f"Assigned {len(checked_ids)} device(s) to {self.account_table.rowCount()} account(s)")
            self.load_main_account_tab()

        save_btn.clicked.connect(_save)
        # Fire _populate_table after the dialog's event loop starts
        QTimer.singleShot(100, _populate_table)
        dialog.exec()
    

    def refresh_devices_in_dialog(self, device_list_widget=None):
        """Refresh devices - kept for compatibility."""
        self.refresh_devices()
    

    def open_automation_settings_dialog(self):
        """Open automation and performance settings dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_automation"))
        dialog.setFixedSize(500, 550)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 12px;
            }
            QSpinBox {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 8px;
                color: #ffffff;
            }
            QCheckBox {
                color: #ffffff;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #555555;
                background-color: #2d2d2d;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4CAF50;
                background-color: #4CAF50;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton#closeBtn {
                background-color: #555555;
            }
            QPushButton#closeBtn:hover {
                background-color: #666666;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Automation & Performance Settings")
        title.setStyleSheet("color: #4CAF50; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Timing Settings
        timing_label = QLabel("Timing Settings:")
        timing_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(timing_label)
        
        delay_label = QLabel("Delay Between Actions (seconds):")
        delay_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        layout.addWidget(delay_label)
        
        delay_spin = QSpinBox()
        delay_spin.setRange(1, 60)
        delay_spin.setValue(self.delay_input.value())
        layout.addWidget(delay_spin)
        
        # Account Creation
        accounts_label = QLabel("Account Creation:")
        accounts_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold; margin-top: 15px;")
        layout.addWidget(accounts_label)
        
        count_label = QLabel("Number of Accounts to Create:")
        count_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        layout.addWidget(count_label)
        
        count_spin = QSpinBox()
        count_spin.setRange(1, 100)
        count_spin.setValue(self.account_count_input.value())
        layout.addWidget(count_spin)
        
        # Performance Options
        perf_label = QLabel("Performance Options:")
        perf_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold; margin-top: 15px;")
        layout.addWidget(perf_label)
        
        parallel_cb = QCheckBox("Enable Parallel Execution")
        parallel_cb.setChecked(self.parallel_execution_checkbox.isChecked())
        layout.addWidget(parallel_cb)
        
        parallel_desc = QLabel("   Run multiple devices simultaneously")
        parallel_desc.setStyleSheet("color: #666666; font-size: 10px; margin-left: 20px;")
        layout.addWidget(parallel_desc)
        
        retry_cb = QCheckBox("Auto-Retry on Failure")
        retry_cb.setChecked(self.auto_retry_checkbox.isChecked())
        layout.addWidget(retry_cb)
        
        retry_desc = QLabel("   Automatically retry failed operations")
        retry_desc.setStyleSheet("color: #666666; font-size: 10px; margin-left: 20px;")
        layout.addWidget(retry_desc)
        
        layout.addStretch()
        
        # Info
        info = QLabel("These settings control automation speed and reliability. Lower delays are faster but may be less stable.")
        info.setStyleSheet("""
            color: #888888;
            font-size: 10px;
            padding: 10px;
            background-color: rgba(76, 175, 80, 0.1);
            border-radius: 6px;
            border: 1px solid #4CAF50;
        """)
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton(" Save Settings")
        save_btn.setIcon(qta.icon('fa5s.save', color='#ffffff'))
        save_btn.clicked.connect(lambda: self.save_automation_settings(
            delay_spin.value(),
            count_spin.value(),
            parallel_cb.isChecked(),
            retry_cb.isChecked(),
            dialog
        ))
        btn_layout.addWidget(save_btn)
        
        close_btn = QPushButton("Cancel")
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()
    

    def save_automation_settings(self, delay, count, parallel, retry, dialog):
        """Save automation settings."""
        self.delay_input.setValue(delay)
        self.account_count_input.setValue(count)
        self.parallel_execution_checkbox.setChecked(parallel)
        self.auto_retry_checkbox.setChecked(retry)
        
        self.update_automation_summary()
        self.add_activity("✓ Automation settings saved")
        QMessageBox.information(dialog, "Success", "Automation settings saved successfully!")
        dialog.accept()
    

    def update_automation_summary(self):
        """Update the automation summary label."""
        if hasattr(self, 'automation_summary_label'):
            delay = self.delay_input.value()
            count = self.account_count_input.value()
            perf = "Parallel" if self.parallel_execution_checkbox.isChecked() else "Standard"
            self.automation_summary_label.setText(f"Delay: {delay}s | Accounts: {count} | Performance: {perf}")
    

    def open_auto_reg_advanced_settings(self):
        """Open advanced settings dialog for Auto Registration."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Advanced Settings")
        dialog.setMinimumWidth(900)
        dialog.setMinimumHeight(550)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
            }
            QLabel {
                color: #cccccc;
                font-size: 11px;
            }
            QLineEdit, QComboBox {
                background-color: #252525;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 10px 12px;
                color: #e0e0e0;
                font-size: 11px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #4CAF50;
                background-color: #2a2a2a;
            }
            QLineEdit:read-only {
                background-color: #222222;
                color: #999999;
            }
            QCheckBox {
                color: #cccccc;
                font-size: 11px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #444444;
                background-color: #252525;
            }
            QCheckBox::indicator:hover {
                border: 1px solid #4CAF50;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 1px solid #4CAF50;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 12px 24px;
                font-size: 12px;
                font-weight: 600;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton#closeBtn {
                background-color: #3a3a3a;
            }
            QPushButton#closeBtn:hover {
                background-color: #444444;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 3-Panel horizontal layout
        panels_container = QWidget()
        panels_container.setStyleSheet("background: #1e1e1e;")
        panels_layout = QHBoxLayout(panels_container)
        panels_layout.setSpacing(0)
        panels_layout.setContentsMargins(0, 0, 0, 0)
        
        # Helper functions for consistent styling
        def _panel():
            p = QWidget()
            p.setStyleSheet("background: #1e1e1e; border-right: 1px solid #2a2a2a;")
            pl = QVBoxLayout(p)
            pl.setSpacing(16)
            pl.setContentsMargins(24, 24, 24, 24)
            return p, pl
        
        def _section(title):
            lbl = QLabel(title)
            lbl.setStyleSheet("color: #4CAF50; font-size: 13px; font-weight: 600; padding-bottom: 8px;")
            return lbl
        
        def _input(placeholder="", text="", readonly=False):
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            inp.setText(text)
            inp.setReadOnly(readonly)
            inp.setFixedHeight(36)
            inp.setStyleSheet("""
                QLineEdit {
                    background: #252525;
                    border: 1px solid #3a3a3a;
                    border-radius: 5px;
                    padding: 0 12px;
                    color: #e0e0e0;
                    font-size: 12px;
                }
                QLineEdit:focus { border-color: #4CAF50; background: #2a2a2a; }
                QLineEdit:hover { border-color: #4a4a4a; }
                QLineEdit:read-only { background: #222; color: #999; }
                QLineEdit:disabled { 
                    background: #1a1a1a; 
                    border-color: #2a2a2a; 
                    color: #666; 
                }
            """)
            return inp
        
        def _combo(items, current=""):
            cb = QComboBox()
            cb.addItems(items)
            if current:
                cb.setCurrentText(current)
            cb.setFixedHeight(36)
            cb.setStyleSheet("""
                QComboBox {
                    background: #252525;
                    border: 1px solid #3a3a3a;
                    border-radius: 5px;
                    padding: 0 12px;
                    color: #e0e0e0;
                    font-size: 12px;
                }
                QComboBox:hover { border-color: #4a4a4a; }
                QComboBox:disabled { 
                    background: #1a1a1a; 
                    border-color: #2a2a2a; 
                    color: #666; 
                }
                QComboBox::drop-down { border: none; width: 22px; }
                QComboBox::down-arrow {
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #888;
                    margin-right: 8px;
                }
                QComboBox::down-arrow:disabled {
                    border-top-color: #444;
                }
                QComboBox QAbstractItemView {
                    background: #252525;
                    border: 1px solid #3a3a3a;
                    color: #e0e0e0;
                    selection-background-color: rgba(76,175,80,0.3);
                }
            """)
            return cb
        
        def _checkbox(text, checked=False, color="#4CAF50"):
            chk = QCheckBox(text)
            chk.setChecked(checked)
            chk.setStyleSheet(f"""
                QCheckBox {{
                    color: #ccc;
                    font-size: 12px;
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 17px;
                    height: 17px;
                    border-radius: 4px;
                    border: 1px solid #444;
                    background: #252525;
                }}
                QCheckBox::indicator:hover {{ border-color: {color}; }}
                QCheckBox::indicator:checked {{
                    background: {color};
                    border-color: {color};
                }}
            """)
            return chk
        
        def _icon_btn(icon, color, size=36):
            btn = QPushButton()
            btn.setIcon(qta.icon(icon, color='#fff'))
            btn.setFixedSize(size, size)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    border: none;
                    border-radius: 5px;
                }}
                QPushButton:hover {{ background: {color}dd; }}
                QPushButton:disabled {{ 
                    background: #1a1a1a; 
                    border: 1px solid #2a2a2a; 
                }}
            """)
            return btn
        
        # ── PANEL 1: Account Info ──
        panel1, p1_layout = _panel()
        p1_layout.addWidget(_section("Account Info"))
        
        # Names with edit button
        names_row = QHBoxLayout()
        names_row.setSpacing(8)
        names_display = _input("Click edit to set names...", self.names_display.text() if hasattr(self, 'names_display') else "", True)
        names_row.addWidget(names_display, 1)
        names_edit_btn = _icon_btn('fa5s.edit', '#4CAF50')
        names_edit_btn.clicked.connect(self.edit_custom_names)
        names_row.addWidget(names_edit_btn)
        p1_layout.addLayout(names_row)
        
        auto_english_cb = _checkbox("Auto generate English names", self.auto_english_names_checkbox.isChecked())
        p1_layout.addWidget(auto_english_cb)
        
        p1_layout.addSpacing(8)
        
        # DOB label
        dob_label = QLabel("Date of Birth")
        dob_label.setStyleSheet("color: #aaa; font-size: 11px; padding-left: 2px;")
        p1_layout.addWidget(dob_label)
        birthday_input = _input("DD/MM/YYYY", self.birthday_input.text())
        p1_layout.addWidget(birthday_input)
        
        p1_layout.addSpacing(4)
        
        # Gender label
        gender_label = QLabel("Gender")
        gender_label.setStyleSheet("color: #aaa; font-size: 11px; padding-left: 2px;")
        p1_layout.addWidget(gender_label)
        gender_combo = _combo(["Male", "Female", "Custom", "Random"], self.gender_input.currentText())
        p1_layout.addWidget(gender_combo)
        
        p1_layout.addStretch()
        
        # ── PANEL 2: Contact ──
        panel2, p2_layout = _panel()
        p2_layout.addWidget(_section("Contact"))
        
        # Toggle row
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(16)
        use_email_cb = _checkbox("Use Email", self.use_email_checkbox.isChecked())
        use_phone_cb = _checkbox("Use Phone", self.use_phone_checkbox.isChecked(), "#FF9800")
        toggle_row.addWidget(use_email_cb)
        toggle_row.addWidget(use_phone_cb)
        toggle_row.addStretch()
        p2_layout.addLayout(toggle_row)
        
        p2_layout.addSpacing(8)
        
        # Email with edit button
        email_row = QHBoxLayout()
        email_row.setSpacing(8)
        email_display = _input("testuser@example.com", self.email_display.text() if hasattr(self, 'email_display') else "", True)
        email_row.addWidget(email_display, 1)
        email_edit_btn = _icon_btn('fa5s.edit', '#4CAF50')
        email_edit_btn.clicked.connect(self.edit_multiple_emails)
        email_row.addWidget(email_edit_btn)
        p2_layout.addLayout(email_row)
        
        p2_layout.addSpacing(8)
        
        random_phone_cb = _checkbox("Random Phone Number", self.random_phone_checkbox.isChecked())
        p2_layout.addWidget(random_phone_cb)
        
        country_combo = _combo([
            "+1 (US/Canada)", "+44 (UK)", "+855 (Cambodia)", "+84 (Vietnam)",
            "+86 (China)", "+91 (India)", "+62 (Indonesia)", "+63 (Philippines)",
            "+66 (Thailand)", "+60 (Malaysia)", "+81 (Japan)", "+82 (South Korea)",
            "+65 (Singapore)", "+61 (Australia)"
        ], self.country_code_input.currentText())
        p2_layout.addWidget(country_combo)
        
        phone_input = _input("Phone number (optional)", self.phone_input.text())
        p2_layout.addWidget(phone_input)
        
        p2_layout.addStretch()
        
        # ── PANEL 3: Security & Settings ──
        panel3, p3_layout = _panel()
        panel3.setStyleSheet("background: #1e1e1e;")  # Remove right border on last panel
        p3_layout.addWidget(_section("Security & Settings"))
        
        # Password with random checkbox
        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(12)
        password_input = _input("Password", self.password_input.text())
        pwd_row.addWidget(password_input, 1)
        random_password_cb = _checkbox("Random", self.random_password_checkbox.isChecked())
        pwd_row.addWidget(random_password_cb)
        p3_layout.addLayout(pwd_row)
        
        p3_layout.addSpacing(8)
        
        # Profile pictures with browse button
        profile_row = QHBoxLayout()
        profile_row.setSpacing(8)
        profile_input = _input("Profile pictures folder (optional)", self.profile_pic_input.text())
        profile_row.addWidget(profile_input, 1)
        browse_btn = _icon_btn('fa5s.folder-open', '#2196F3')
        browse_btn.clicked.connect(lambda: self.browse_profile_folder_dialog(profile_input))
        profile_row.addWidget(browse_btn)
        p3_layout.addLayout(profile_row)
        
        p3_layout.addSpacing(8)
        
        reg_novary_cb = _checkbox("Reg Novary (No Variation)", self.reg_novary_checkbox.isChecked())
        p3_layout.addWidget(reg_novary_cb)
        
        verification_cb = _checkbox("Verification", self.verification_checkbox.isChecked(), "#FF9800")
        p3_layout.addWidget(verification_cb)
        
        p3_layout.addStretch()
        
        # Add panels
        panels_layout.addWidget(panel1, 1)
        panels_layout.addWidget(panel2, 1)
        panels_layout.addWidget(panel3, 1)
        
        layout.addWidget(panels_container, 1)
        
        # ── Interaction Logic ──
        def update_reg_novary_state():
            """When Reg Novary is checked, disable variation fields and uncheck Verification"""
            is_novary = reg_novary_cb.isChecked()
            if is_novary:
                verification_cb.setChecked(False)  # Mutually exclusive
            # Disable only profile pictures - password randomization is still allowed
            profile_input.setEnabled(not is_novary)
            browse_btn.setEnabled(not is_novary)
        
        def update_verification_state():
            """When Verification is checked, uncheck Reg Novary"""
            if verification_cb.isChecked():
                reg_novary_cb.setChecked(False)  # Mutually exclusive
        
        def update_email_phone_state():
            """Enable/disable email and phone fields based on selection - mutually exclusive"""
            email_enabled = use_email_cb.isChecked()
            phone_enabled = use_phone_cb.isChecked()
            
            # Make them mutually exclusive
            if email_enabled and phone_enabled:
                # If both are checked, uncheck the other one based on which was just clicked
                sender = dialog.sender() if hasattr(dialog, 'sender') else None
                if sender == use_email_cb:
                    use_phone_cb.setChecked(False)
                    phone_enabled = False
                elif sender == use_phone_cb:
                    use_email_cb.setChecked(False)
                    email_enabled = False
            
            # Ensure at least one is selected
            if not email_enabled and not phone_enabled:
                use_email_cb.setChecked(True)
                email_enabled = True
            
            # Email fields
            email_display.setEnabled(email_enabled)
            email_edit_btn.setEnabled(email_enabled)
            
            # Phone fields
            random_phone_cb.setEnabled(phone_enabled)
            country_combo.setEnabled(phone_enabled)
            phone_input.setEnabled(phone_enabled)
        
        def update_random_password_state():
            """When random password is checked, disable password input"""
            password_input.setEnabled(not random_password_cb.isChecked())
        
        def update_random_phone_state():
            """When random phone is checked, disable phone input"""
            phone_input.setEnabled(not random_phone_cb.isChecked())
        
        # Connect signals
        reg_novary_cb.toggled.connect(update_reg_novary_state)
        verification_cb.toggled.connect(update_verification_state)
        use_email_cb.toggled.connect(update_email_phone_state)
        use_phone_cb.toggled.connect(update_email_phone_state)
        random_password_cb.toggled.connect(update_random_password_state)
        random_phone_cb.toggled.connect(update_random_phone_state)
        
        # Initialize states
        update_reg_novary_state()
        update_email_phone_state()
        update_random_password_state()
        update_random_phone_state()
        
        # Footer
        footer = QWidget()
        footer.setStyleSheet("background: #1a1a1a; border-top: 1px solid #2a2a2a;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()
        
        close_btn = QPushButton("Cancel")
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedHeight(38)
        close_btn.setFixedWidth(100)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #f44336;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover { background: #d32f2f; }
        """)
        close_btn.clicked.connect(dialog.reject)
        footer_layout.addWidget(close_btn)
        
        save_btn = QPushButton("  Save Settings")
        save_btn.setIcon(qta.icon('fa5s.check', color='#fff'))
        save_btn.setFixedHeight(38)
        save_btn.setFixedWidth(140)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover { background: #45a049; }
        """)
        save_btn.clicked.connect(lambda: self.save_auto_reg_advanced_settings(
            auto_english_cb.isChecked(),
            birthday_input.text(),
            gender_combo.currentText(),
            profile_input.text(),
            reg_novary_cb.isChecked(),
            verification_cb.isChecked(),
            random_phone_cb.isChecked(),
            country_combo.currentText(),
            phone_input.text(),
            use_email_cb.isChecked(),
            use_phone_cb.isChecked(),
            password_input.text(),
            random_password_cb.isChecked(),
            dialog
        ))
        footer_layout.addWidget(save_btn)
        
        layout.addWidget(footer)
        
        dialog.exec()
    

    def browse_profile_folder_dialog(self, line_edit):
        """Browse for profile pictures folder from dialog."""
        folder = QFileDialog.getExistingDirectory(self, "Select Profile Pictures Folder")
        if folder:
            line_edit.setText(folder)
    
    

    def save_auto_reg_advanced_settings(self, auto_english_names, birthday, gender, profile_folder, reg_novary, verification, random_phone, country_code, phone_number, use_email, use_phone, password, random_password, dialog):
        """Save advanced registration settings."""
        self.auto_english_names_checkbox.setChecked(auto_english_names)
        self.birthday_input.setText(birthday)
        self.gender_input.setCurrentText(gender)
        self.profile_pic_input.setText(profile_folder)
        self.reg_novary_checkbox.setChecked(reg_novary)
        self.verification_checkbox.setChecked(verification)
        
        # Save phone settings
        self.random_phone_checkbox.setChecked(random_phone)
        self.country_code_input.setCurrentText(country_code)
        self.phone_input.setText(phone_number)
        
        # Save signup method
        self.use_email_checkbox.setChecked(use_email)
        self.use_phone_checkbox.setChecked(use_phone)
        
        # Save password settings
        self.password_input.setText(password)
        self.random_password_checkbox.setChecked(random_password)
        
        self.add_activity("✓ Advanced settings saved")
        QMessageBox.information(dialog, "Success", "Advanced settings saved successfully!")
        dialog.accept()
    

    def _get_current_device_info(self, device_id):
        """Get current device information for comparison."""
        import subprocess
        
        info = {"device_id": device_id}
        
        try:
            # Get basic device properties
            properties = [
                ("manufacturer", "ro.product.manufacturer"),
                ("model", "ro.product.model"),
                ("brand", "ro.product.brand"),
                ("device_name", "ro.product.name"),
                ("android_version", "ro.build.version.release"),
                ("android_sdk", "ro.build.version.sdk"),
                ("build_fingerprint", "ro.build.fingerprint"),
                ("serial_number", "ro.serialno"),
            ]
            
            for key, prop in properties:
                try:
                    result = safe_subprocess_run([
                        self.adb_path, '-s', device_id, 'shell', f'getprop {prop}'
                    ], capture_output=True, text=True, timeout=3)
                    
                    if result.returncode == 0:
                        value = result.stdout.strip()
                        if value and value != 'unknown':
                            info[key] = value
                except:
                    info[key] = "Unknown"
            
        except Exception as e:
            self.add_activity(f"⚠️ Could not get current device info: {e}")
        
        return info
    

    def _apply_test_changes(self, device_id, fake_info, dialog):
        """Apply device changes from test dialog."""
        try:
            dialog.accept()  # Close dialog first
            
            # Show confirmation
            reply = QMessageBox.question(
                self, 
                "Apply Device Changes", 
                "This will apply the device changes to your Android device.\n\n"
                "⚠️ WARNING: This may require root access and could potentially\n"
                "affect your device. Make sure you understand the risks.\n\n"
                "Do you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._apply_real_device_changes(device_id, fake_info)
                QMessageBox.information(
                    self, 
                    "Device Changes Applied", 
                    "Device changes have been applied successfully!\n\n"
                    "The changes will take effect for new app installations.\n"
                    "Facebook Lite will use the new device identity."
                )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply changes:\n{e}")
    

    def generate_fake_device_info(self):
        """Generate realistic fake device information for anti-detection."""
        import random
        import string
        import hashlib
        import time
        
        # More comprehensive and realistic device database
        device_models = [
            # Samsung Galaxy Series (Most popular)
            ("Samsung", "SM-G973F", "beyond1lte", "Galaxy S10", "samsung"),
            ("Samsung", "SM-G975F", "beyond2lte", "Galaxy S10+", "samsung"),
            ("Samsung", "SM-G981B", "x1s", "Galaxy S20", "samsung"),
            ("Samsung", "SM-G991B", "o1s", "Galaxy S21", "samsung"),
            ("Samsung", "SM-G996B", "t2s", "Galaxy S21+", "samsung"),
            ("Samsung", "SM-G998B", "p3s", "Galaxy S21 Ultra", "samsung"),
            ("Samsung", "SM-A515F", "a51", "Galaxy A51", "samsung"),
            ("Samsung", "SM-A525F", "a52q", "Galaxy A52", "samsung"),
            ("Samsung", "SM-A715F", "a71", "Galaxy A71", "samsung"),
            ("Samsung", "SM-N975F", "d2s", "Galaxy Note10+", "samsung"),
            ("Samsung", "SM-N986B", "c2s", "Galaxy Note20 Ultra", "samsung"),
            
            # Xiaomi/Redmi Series
            ("Xiaomi", "M2101K6G", "venus", "Mi 11", "Xiaomi"),
            ("Xiaomi", "M2007J20CG", "apollo", "Mi 10T", "Xiaomi"),
            ("Xiaomi", "M2006C3MG", "merlin", "Redmi Note 9", "Redmi"),
            ("Xiaomi", "M2010J19CG", "joyeuse", "Redmi Note 9 Pro", "Redmi"),
            ("Xiaomi", "M2012K11AG", "haydn", "Mi 11 Pro", "Xiaomi"),
            ("Xiaomi", "21081111RG", "lisa", "Mi 11 Lite", "Xiaomi"),
            ("Xiaomi", "M2004J19C", "lmi", "POCO F2 Pro", "POCO"),
            ("Xiaomi", "M2102J20SG", "alioth", "POCO F3", "POCO"),
            
            # OnePlus Series
            ("OnePlus", "LE2117", "OnePlus9", "OnePlus 9", "OnePlus"),
            ("OnePlus", "LE2115", "OnePlus9Pro", "OnePlus 9 Pro", "OnePlus"),
            ("OnePlus", "HD1903", "OnePlus7T", "OnePlus 7T", "OnePlus"),
            ("OnePlus", "HD1905", "OnePlus7TPro", "OnePlus 7T Pro", "OnePlus"),
            ("OnePlus", "IN2023", "OnePlus8T", "OnePlus 8T", "OnePlus"),
            
            # Google Pixel Series
            ("Google", "Pixel 4", "flame", "Pixel 4", "google"),
            ("Google", "Pixel 4 XL", "coral", "Pixel 4 XL", "google"),
            ("Google", "Pixel 5", "redfin", "Pixel 5", "google"),
            ("Google", "Pixel 6", "oriole", "Pixel 6", "google"),
            ("Google", "Pixel 6 Pro", "raven", "Pixel 6 Pro", "google"),
            
            # Huawei Series
            ("Huawei", "ELE-L29", "HWELE", "P30", "HUAWEI"),
            ("Huawei", "VOG-L29", "HWVOG", "P30 Pro", "HUAWEI"),
            ("Huawei", "ANA-NX9", "HWANA", "P40", "HUAWEI"),
            ("Huawei", "ELS-NX9", "HWELS", "P40 Pro", "HUAWEI"),
            
            # Oppo Series
            ("Oppo", "CPH2025", "OP4F2F", "Find X2", "OPPO"),
            ("Oppo", "CPH2173", "OP4F85", "Find X3", "OPPO"),
            ("Oppo", "CPH2127", "OP4EC1", "Reno4", "OPPO"),
            
            # Vivo Series
            ("Vivo", "V2040", "PD2040", "X60", "vivo"),
            ("Vivo", "V2045", "PD2045", "X60 Pro", "vivo"),
            ("Vivo", "V2031", "PD2031", "V20", "vivo"),
        ]
        
        # Realistic Android versions with proper SDK mapping
        android_versions = [
            ("10", "29", "Q"),
            ("11", "30", "R"), 
            ("12", "31", "S"),
            ("12", "32", "S"),
            ("13", "33", "T"),
            ("14", "34", "U"),
        ]
        
        # Select random device
        manufacturer, model, device_name, marketing_name, brand = random.choice(device_models)
        android_version, sdk_version, android_codename = random.choice(android_versions)
        
        # Generate realistic identifiers
        def generate_android_id():
            # Android ID should be 16 hex characters
            return ''.join(random.choices('0123456789abcdef', k=16))
        
        def generate_serial():
            # More realistic serial patterns
            if manufacturer == "Samsung":
                return f"R58{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
            elif manufacturer == "Xiaomi":
                return f"{''.join(random.choices(string.digits, k=10))}"
            elif manufacturer == "OnePlus":
                return f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
            else:
                return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        
        def generate_mac_address():
            # Use realistic OUI (Organizationally Unique Identifier) prefixes
            oui_prefixes = {
                "Samsung": ["28:6D:CD", "34:23:BA", "40:4E:36", "5C:0A:5B"],
                "Xiaomi": ["34:CE:00", "64:09:80", "78:02:F8", "8C:BE:BE"],
                "OnePlus": ["AC:37:43", "E8:B2:AC", "F0:79:59", "F8:A9:D0"],
                "Google": ["DA:A1:19", "F4:F5:E8", "64:16:66", "AC:37:43"],
                "Huawei": ["00:E0:FC", "28:6D:CD", "70:72:3C", "C8:94:02"],
                "Oppo": ["A4:50:46", "AC:E2:D3", "C4:04:15", "E0:B9:4D"],
                "Vivo": ["70:F3:95", "8C:BE:BE", "A4:50:46", "E8:B2:AC"]
            }
            
            prefix = random.choice(oui_prefixes.get(manufacturer, ["02:00:00"]))
            suffix = ':'.join(['%02x' % random.randint(0, 255) for _ in range(3)])
            return f"{prefix}:{suffix}"
        
        def generate_build_fingerprint():
            # Realistic build fingerprint format
            build_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            build_number = ''.join(random.choices(string.digits, k=10))
            
            return f"{brand}/{device_name}/{device_name}:{android_version}/{build_id}/{build_number}:user/release-keys"
        
        def generate_build_id():
            # Realistic build ID patterns
            if manufacturer == "Samsung":
                return f"{android_codename}{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
            elif manufacturer == "Xiaomi":
                return f"{''.join(random.choices(string.ascii_uppercase, k=3))}{''.join(random.choices(string.digits, k=3))}"
            else:
                return f"{android_codename}{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
        
        def generate_imei():
            # Generate realistic IMEI (15 digits)
            # First 8 digits are TAC (Type Allocation Code)
            tac_codes = {
                "Samsung": ["35328409", "35161509", "35699309"],
                "Xiaomi": ["86006004", "86006104", "86006204"],
                "OnePlus": ["86177603", "86177703", "86177803"],
                "Google": ["35161511", "35328411", "35699311"],
                "Huawei": ["86006304", "86006404", "86006504"],
                "Oppo": ["86006604", "86006704", "86006804"],
                "Vivo": ["86006904", "86007004", "86007104"]
            }
            
            tac = random.choice(tac_codes.get(manufacturer, ["86000000"]))
            # Next 6 digits are serial number
            serial_part = ''.join(random.choices(string.digits, k=6))
            # Last digit is check digit (Luhn algorithm)
            imei_partial = tac + serial_part
            
            # Calculate Luhn check digit
            def luhn_checksum(card_num):
                def digits_of(n):
                    return [int(d) for d in str(n)]
                digits = digits_of(card_num)
                odd_digits = digits[-1::-2]
                even_digits = digits[-2::-2]
                checksum = sum(odd_digits)
                for d in even_digits:
                    checksum += sum(digits_of(d*2))
                return checksum % 10
            
            check_digit = (10 - luhn_checksum(int(imei_partial))) % 10
            return imei_partial + str(check_digit)
        
        # Generate realistic screen specifications
        screen_specs = {
            "Samsung": [
                ("1440x3200", 550, "6.8"),
                ("1080x2400", 420, "6.2"),
                ("1080x2340", 420, "6.1"),
            ],
            "Xiaomi": [
                ("1080x2400", 395, "6.67"),
                ("1080x2340", 395, "6.53"),
                ("720x1600", 270, "6.53"),
            ],
            "OnePlus": [
                ("1440x3216", 516, "6.78"),
                ("1080x2400", 402, "6.55"),
            ],
            "Google": [
                ("1080x2340", 444, "5.8"),
                ("1440x3040", 537, "6.3"),
            ]
        }
        
        screen_resolution, screen_density, screen_size = random.choice(
            screen_specs.get(manufacturer, [("1080x2340", 420, "6.1")])
        )
        
        # Generate realistic hardware specs
        ram_options = [3072, 4096, 6144, 8192, 12288]  # 3GB, 4GB, 6GB, 8GB, 12GB
        storage_options = [64, 128, 256, 512]  # GB
        
        fake_info = {}
        
        # Only include enabled options
        if self.change_android_id_checkbox.isChecked():
            fake_info['android_id'] = generate_android_id()
        
        if self.change_device_model_checkbox.isChecked():
            fake_info['manufacturer'] = manufacturer
            fake_info['model'] = model
            fake_info['device_name'] = device_name
            fake_info['marketing_name'] = marketing_name
            fake_info['brand'] = brand
        
        if self.change_build_fingerprint_checkbox.isChecked():
            fake_info['build_fingerprint'] = generate_build_fingerprint()
            fake_info['build_id'] = generate_build_id()
        
        if self.change_serial_checkbox.isChecked():
            fake_info['serial_number'] = generate_serial()
        
        if self.change_mac_address_checkbox.isChecked():
            fake_info['mac_address'] = generate_mac_address()
        
        # Always include these for completeness
        fake_info.update({
            'android_version': android_version,
            'android_sdk': sdk_version,
            'android_codename': android_codename,
            'device_screen_size': screen_resolution,
            'device_screen_density': screen_density,
            'screen_size_inches': screen_size,
            'cpu_architecture': random.choice(["arm64-v8a", "armeabi-v7a"]),
            'total_ram_mb': random.choice(ram_options),
            'storage_gb': random.choice(storage_options),
            'imei': generate_imei(),
            'build_date': int(time.time()) - random.randint(86400*30, 86400*365),  # 30 days to 1 year ago
            'security_patch': f"2023-{random.randint(1,12):02d}-01",
            'bootloader_version': f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}",
            'baseband_version': f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=12))}",
        })
        
        return fake_info
    

    def apply_device_changer_to_registration(self, registration):
        """Apply device changer settings to a registration instance."""
        if not self.enable_device_changer_checkbox.isChecked():
            return
        
        try:
            # Generate fake device info
            fake_info = self.generate_fake_device_info()
            
            # Store the fake info in the registration instance
            registration.fake_device_info = fake_info
            
            # Apply actual device changes to the Android device
            self._apply_real_device_changes(registration.device_name, fake_info)
            
            self.add_activity(f"🔄 Applied device changer to {registration.device_name[-8:]}")
            
        except Exception as e:
            self.add_activity(f"❌ Device changer failed: {e}")
    

    def _apply_real_device_changes(self, device_id, fake_info):
        """Actually modify device properties on the Android device."""
        import subprocess
        import os
        
        try:
            self.add_activity("🔧 Applying real device changes...")
            
            # Check if device is rooted (required for most changes)
            result = safe_subprocess_run(
                [self.adb_path, '-s', device_id, 'shell', 'su -c "echo test"'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            is_rooted = result.returncode == 0 and 'test' in result.stdout
            
            if not is_rooted:
                self.add_activity("⚠️ Device not rooted - using limited device spoofing")
                self._apply_non_root_changes(device_id, fake_info)
                return
            
            self.add_activity("✅ Root access detected - applying full device spoofing")
            
            # Apply Android ID change
            if 'android_id' in fake_info and self.change_android_id_checkbox.isChecked():
                self._change_android_id(device_id, fake_info['android_id'])
            
            # Apply build properties changes
            if self.change_device_model_checkbox.isChecked():
                self._change_build_properties(device_id, fake_info)
            
            # Apply MAC address change
            if 'mac_address' in fake_info and self.change_mac_address_checkbox.isChecked():
                self._change_mac_address(device_id, fake_info['mac_address'])
            
            # Apply serial number change
            if 'serial_number' in fake_info and self.change_serial_checkbox.isChecked():
                self._change_serial_number(device_id, fake_info['serial_number'])
            
            self.add_activity("✅ Device changes applied successfully")
            
        except Exception as e:
            self.add_activity(f"❌ Failed to apply device changes: {e}")
    

    def _apply_non_root_changes(self, device_id, fake_info):
        """Apply device changes that don't require root access."""
        try:
            # For non-rooted devices, we can only change app-level properties
            # This is still effective for many detection methods
            
            # Create a temporary script to modify app behavior
            script_content = f"""
# Device Changer Script - Non-Root Mode
# This modifies app-detectable properties

# Clear app data to reset device fingerprint
pm clear com.facebook.lite 2>/dev/null || true

# Set fake device properties for apps (using setprop if available)
setprop debug.fake.manufacturer "{fake_info.get('manufacturer', 'Samsung')}" 2>/dev/null || true
setprop debug.fake.model "{fake_info.get('model', 'SM-G973F')}" 2>/dev/null || true
setprop debug.fake.brand "{fake_info.get('brand', 'samsung')}" 2>/dev/null || true

echo "Non-root device changes applied"
"""
            
            # Write script to device
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                f.write(script_content)
                temp_script = f.name
            
            # Push script to device
            safe_subprocess_run([
                self.adb_path, '-s', device_id, 'push', 
                temp_script, '/data/local/tmp/device_changer.sh'
            ], capture_output=True, timeout=10)
            
            # Execute script
            safe_subprocess_run([
                self.adb_path, '-s', device_id, 'shell', 
                'chmod 755 /data/local/tmp/device_changer.sh && /data/local/tmp/device_changer.sh'
            ], capture_output=True, timeout=10)
            
            # Clean up
            os.unlink(temp_script)
            safe_subprocess_run([
                self.adb_path, '-s', device_id, 'shell', 
                'rm /data/local/tmp/device_changer.sh'
            ], capture_output=True, timeout=5)
            
            self.add_activity("✅ Non-root device changes applied")
            
        except Exception as e:
            self.add_activity(f"⚠️ Non-root changes failed: {e}")
    

    def _change_android_id(self, device_id, new_android_id):
        """Change Android ID (requires root)."""
        try:
            # Android ID is stored in settings database
            cmd = f'su -c "settings put secure android_id {new_android_id}"'
            result = safe_subprocess_run([
                self.adb_path, '-s', device_id, 'shell', cmd
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.add_activity(f"✅ Android ID changed to: {new_android_id}")
            else:
                self.add_activity(f"⚠️ Android ID change failed: {result.stderr}")
                
        except Exception as e:
            self.add_activity(f"❌ Android ID change error: {e}")
    

    def _change_build_properties(self, device_id, fake_info):
        """Change build properties (requires root)."""
        try:
            # Backup original build.prop
            safe_subprocess_run([
                self.adb_path, '-s', device_id, 'shell', 
                'su -c "cp /system/build.prop /system/build.prop.backup"'
            ], capture_output=True, timeout=10)
            
            # Mount system as writable
            safe_subprocess_run([
                self.adb_path, '-s', device_id, 'shell', 
                'su -c "mount -o remount,rw /system"'
            ], capture_output=True, timeout=10)
            
            # Change properties
            properties_to_change = {
                'ro.product.manufacturer': fake_info.get('manufacturer', 'Samsung'),
                'ro.product.model': fake_info.get('model', 'SM-G973F'),
                'ro.product.brand': fake_info.get('brand', 'samsung'),
                'ro.product.name': fake_info.get('device_name', 'beyond1lte'),
                'ro.build.fingerprint': fake_info.get('build_fingerprint', ''),
                'ro.serialno': fake_info.get('serial_number', ''),
            }
            
            for prop, value in properties_to_change.items():
                if value:
                    cmd = f'su -c "sed -i \'s/^{prop}=.*/{prop}={value}/\' /system/build.prop"'
                    safe_subprocess_run([
                        self.adb_path, '-s', device_id, 'shell', cmd
                    ], capture_output=True, timeout=5)
            
            # Mount system as read-only
            safe_subprocess_run([
                self.adb_path, '-s', device_id, 'shell', 
                'su -c "mount -o remount,ro /system"'
            ], capture_output=True, timeout=10)
            
            self.add_activity("✅ Build properties changed")
            
        except Exception as e:
            self.add_activity(f"❌ Build properties change error: {e}")
    

    def _change_mac_address(self, device_id, new_mac):
        """Change MAC address (requires root)."""
        try:
            # This is device-specific and may not work on all devices
            cmd = f'su -c "ifconfig wlan0 hw ether {new_mac}"'
            result = safe_subprocess_run([
                self.adb_path, '-s', device_id, 'shell', cmd
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.add_activity(f"✅ MAC address changed to: {new_mac}")
            else:
                self.add_activity(f"⚠️ MAC address change may not be supported on this device")
                
        except Exception as e:
            self.add_activity(f"❌ MAC address change error: {e}")
    

    def _change_serial_number(self, device_id, new_serial):
        """Change serial number (requires root)."""
        try:
            # Serial is usually in build.prop, handled by _change_build_properties
            self.add_activity(f"✅ Serial number will be changed with build properties")
            
        except Exception as e:
            self.add_activity(f"❌ Serial number change error: {e}")
    

    def get_device_changer_settings(self):
        """Get current device changer settings."""
        return {
            'enabled': self.enable_device_changer_checkbox.isChecked(),
            'change_android_id': self.change_android_id_checkbox.isChecked(),
            'change_device_model': self.change_device_model_checkbox.isChecked(),
            'change_build_fingerprint': self.change_build_fingerprint_checkbox.isChecked(),
            'change_serial': self.change_serial_checkbox.isChecked(),
            'change_mac_address': self.change_mac_address_checkbox.isChecked(),
        }
    
