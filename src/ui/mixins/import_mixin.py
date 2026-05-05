"""
ImportMixin — Import Mixin methods.

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

import os, json, subprocess, threading, time, shutil, tempfile, re, tarfile, csv

from src.i18n.engine import (
    translate as _T, register_widget as _reg,
    _CURRENT_LANG, _get_khmer_font, _REGISTRY as _I18N_REGISTRY,
)
from src.i18n.translations import TRANSLATIONS
from src.automation.url_normalizer import normalize_facebook_url, URL_TYPE_LABELS as _URL_TYPE_LABELS
from src.core.config import CONFIG_FILE

# Project root — 3 levels up from src/ui/mixins/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.core.subprocess_utils import safe_subprocess_run

class ImportMixin:
    """Mixin — methods are injected into MainWindow via multiple inheritance."""

    def _on_custom_text_changed(self):
        """Handle custom text changes with debounce"""
        # Clear any existing timer
        if hasattr(self, '_custom_text_timer'):
            self._custom_text_timer.stop()
        
        # Create new timer for debounced validation (500ms delay)
        self._custom_text_timer = QTimer()
        self._custom_text_timer.setSingleShot(True)
        self._custom_text_timer.timeout.connect(self._auto_validate_custom_text)
        self._custom_text_timer.start(500)
    
    def _auto_validate_custom_text(self):
        """Auto-validate custom text after debounce"""
        if hasattr(self, 'import_type_custom') and self.import_type_custom.isChecked():
            text = self.import_custom_text.toPlainText().strip()
            if text and len(text) > 10:  # Only validate if meaningful content
                self.validate_custom_paste()

    def toggle_import_mode(self):
        """Toggle between File/Folder/Custom import modes"""
        if self.import_type_custom.isChecked():
            # Show custom paste area, hide file path and browse button
            self.import_file_path.setVisible(False)
            self.import_browse_btn.setVisible(False)
            self.import_custom_text.setVisible(True)
            self.file_info_label.setVisible(False)
            # Auto-validate if text already exists
            if self.import_custom_text.toPlainText().strip():
                self.validate_custom_paste()
        else:
            # Show file path and browse button, hide custom paste area
            self.import_file_path.setVisible(True)
            self.import_browse_btn.setVisible(True)
            self.import_custom_text.setVisible(False)

    def browse_import_file(self):
        """Browse for import file or folder"""
        if self.import_type_folder.isChecked():
            folder_path = QFileDialog.getExistingDirectory(
                self, "Select Account Folder or Parent Folder", ""
            )

            if folder_path:
                self.import_file_path.setText(folder_path)
                self.file_info_label.setText("🔍 Scanning folder...")
                self.file_info_label.setVisible(True)
                self.import_accounts_btn.setEnabled(False)

                import threading as _t
                def _scan():
                    account_folders = self._find_account_folders(folder_path)
                    acc_count = len(account_folders)
                    all_accounts = []
                    if acc_count > 0:
                        for acc_folder in account_folders:
                            acc_info_path = None
                            for fname in os.listdir(acc_folder):
                                if fname.lower() in ('acc info', 'acc info.txt'):
                                    acc_info_path = os.path.join(acc_folder, fname)
                                    break
                            if acc_info_path:
                                all_accounts.extend(self._parse_acc_info(acc_info_path))
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self._apply_browse_folder_result(all_accounts, acc_count, account_folders))

                _t.Thread(target=_scan, daemon=True).start()
        else:
            # Browse for file (CSV/JSON)
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Import File", "",
                "CSV Files (*.csv);;JSON Files (*.json);;All Files (*.*)"
            )
            if file_path:
                self.import_file_path.setText(file_path)
                file_size = os.path.getsize(file_path) / 1024
                file_name = os.path.basename(file_path)
                self.file_info_label.setText(f"📄 {file_name} ({file_size:.1f} KB)")
                self.file_info_label.setVisible(True)
                self.preview_import_file(file_path)
                self.import_stats_label.setText("File loaded - Click Validate to check")

    def _apply_browse_folder_result(self, all_accounts, acc_count, account_folders):
        """Apply folder scan results to UI on main thread."""
        import re as _re
        total = len(all_accounts)
        if acc_count > 0 and total > 0:
            self.file_info_label.setText(f"📁 Found {total} account(s) in {acc_count} folder(s)")
            self.validation_label.setText(f"✅ Ready to import {total} account(s)\nClick 'Import Accounts' to start")
            self.validation_label.setStyleSheet("color: #89d185; font-size: 11px;")
            self.import_accounts_btn.setEnabled(True)
            self.import_stats_label.setText(f"{total} accounts ready")

            cookie_keys_ordered = ['c_user', 'xs', 'fr', 'datr', 'sb', 'wd', 'locale']
            all_cookie_keys = list(cookie_keys_ordered)
            for acc in all_accounts:
                for m in _re.finditer(r'(\w+)=', acc.get('cookies', '')):
                    k = m.group(1)
                    if k not in all_cookie_keys:
                        all_cookie_keys.append(k)

            all_cols = ["UID", "Password"] + all_cookie_keys + ["Device Info", "Profile Info"]
            self.import_preview_table.setColumnCount(len(all_cols))
            self.import_preview_table.setHorizontalHeaderLabels(all_cols)
            self.import_preview_table.setRowCount(0)

            for i, acc in enumerate(all_accounts[:10]):
                self.import_preview_table.insertRow(i)
                uid = acc.get('uid', '')
                cookies = acc.get('cookies', '')
                cookie_dict = {}
                for part in _re.split(r';\s*', cookies):
                    if '=' in part:
                        k, v = part.split('=', 1)
                        cookie_dict[k.strip()] = v.strip()
                has_device = '✓' if any(
                    uid in f for af in account_folders
                    if os.path.exists(os.path.join(af, 'Device info'))
                    for f in os.listdir(os.path.join(af, 'Device info'))
                ) else '—'
                has_profile = '✓' if any(
                    uid in f for af in account_folders
                    if os.path.exists(os.path.join(af, 'Profile info'))
                    for f in os.listdir(os.path.join(af, 'Profile info'))
                ) else '—'
                self.import_preview_table.setItem(i, 0, QTableWidgetItem(uid))
                self.import_preview_table.setItem(i, 1, QTableWidgetItem(acc.get('password', '')))
                for col_idx, key in enumerate(all_cookie_keys):
                    self.import_preview_table.setItem(i, 2 + col_idx, QTableWidgetItem(cookie_dict.get(key, '')))
                self.import_preview_table.setItem(i, 2 + len(all_cookie_keys), QTableWidgetItem(has_device))
                self.import_preview_table.setItem(i, 3 + len(all_cookie_keys), QTableWidgetItem(has_profile))
            self.preview_info_label.setText(f"Showing {min(total, 10)} of {total} accounts")
        else:
            self.file_info_label.setText("⚠️ No account folders found")
            self.validation_label.setText("❌ No accounts found\n\nSelect a folder containing 'Acc info' files")
            self.validation_label.setStyleSheet("color: #f48771; font-size: 11px;")
            self.import_accounts_btn.setEnabled(False)
            self.preview_info_label.setText("No accounts to preview")
    

    def open_import_advanced_settings(self):
        """Open advanced import settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_import_adv"))
        dialog.setModal(True)
        dialog.setFixedWidth(460)
        dialog.setStyleSheet("QDialog { background: #1e1e1e; }")

        root = QVBoxLayout(dialog)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setObjectName("aisHdr")
        hdr.setFixedHeight(52)
        hdr.setStyleSheet("QFrame#aisHdr { background: #252526; border: none; border-bottom: 1px solid #2a2a2a; }")
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(20, 0, 20, 0)
        hdr_l.setSpacing(10)
        hdr_ico = QLabel()
        hdr_ico.setPixmap(qta.icon('fa5s.file-import', color='#4CAF50').pixmap(14, 14))
        hdr_ico.setStyleSheet("background: transparent;")
        hdr_l.addWidget(hdr_ico)
        hdr_ttl = QLabel("Advanced Import Settings")
        hdr_ttl.setStyleSheet("color: #cccccc; font-size: 13px; font-weight: bold; background: transparent;")
        hdr_l.addWidget(hdr_ttl)
        hdr_l.addStretch()
        root.addWidget(hdr)

        # Body
        body = QWidget()
        body.setStyleSheet("background: #1e1e1e;")
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(20, 20, 20, 20)
        body_l.setSpacing(12)

        _lbl = "color: #666666; font-size: 10px; font-weight: bold; letter-spacing: 0.6px; background: transparent;"
        _combo = """
            QComboBox { background: #252526; border: 1px solid #3d3d3d; border-radius: 4px; padding: 0 10px; color: #cccccc; font-size: 12px; }
            QComboBox:hover { border-color: #4CAF50; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #888888; margin-right: 8px; }
            QComboBox QAbstractItemView { background: #252526; border: 1px solid #3d3d3d; color: #cccccc; selection-background-color: #2a4a2a; outline: none; }
        """

        fmt_lbl = QLabel("FORMAT TYPE"); fmt_lbl.setStyleSheet(_lbl)
        body_l.addWidget(fmt_lbl)
        format_combo = QComboBox()
        format_combo.addItems(["CSV (Standard)", "JSON (Backup)", "Custom Format"])
        format_combo.setCurrentText(self.import_format_type)
        format_combo.setFixedHeight(34)
        format_combo.setStyleSheet(_combo)
        body_l.addWidget(format_combo)

        delim_lbl = QLabel("DELIMITER"); delim_lbl.setStyleSheet(_lbl)
        body_l.addWidget(delim_lbl)
        delimiter_combo = QComboBox()
        delimiter_combo.addItems(["Comma (,)", "Semicolon (;)", "Tab", "Pipe (|)"])
        delim_map = {",": 0, ";": 1, "\t": 2, "|": 3}
        delimiter_combo.setCurrentIndex(delim_map.get(self.import_delimiter, 0))
        delimiter_combo.setFixedHeight(34)
        delimiter_combo.setStyleSheet(_combo)
        body_l.addWidget(delimiter_combo)

        has_header_check = QCheckBox("First row contains headers")
        has_header_check.setChecked(self.import_has_header)
        has_header_check.setStyleSheet("""
            QCheckBox { color: #cccccc; font-size: 12px; spacing: 8px; background: transparent; }
            QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #3d3d3d; border-radius: 3px; background: #252526; }
            QCheckBox::indicator:checked { background: #4CAF50; border-color: #4CAF50; }
            QCheckBox::indicator:hover { border-color: #4CAF50; }
        """)
        body_l.addWidget(has_header_check)

        info_frame = QFrame()
        info_frame.setObjectName("aisInfo")
        info_frame.setStyleSheet("QFrame#aisInfo { background: #1a2a1a; border: 1px solid #2a3a2a; border-radius: 5px; }")
        info_fl = QHBoxLayout(info_frame)
        info_fl.setContentsMargins(12, 8, 12, 8)
        info_fl.setSpacing(8)
        info_ico2 = QLabel()
        info_ico2.setPixmap(qta.icon('fa5s.info-circle', color='#4CAF50').pixmap(12, 12))
        info_ico2.setStyleSheet("background: transparent;")
        info_fl.addWidget(info_ico2, 0, Qt.AlignmentFlag.AlignTop)
        info_txt = QLabel("Expected columns: UID, Name, Email, Phone, Password, Birthday, Gender, Device, Status, Notes")
        info_txt.setStyleSheet("color: #4CAF50; font-size: 11px; background: transparent;")
        info_txt.setWordWrap(True)
        info_fl.addWidget(info_txt, 1)
        body_l.addWidget(info_frame)
        body_l.addStretch()
        root.addWidget(body, 1)

        # Footer
        ftr = QFrame()
        ftr.setObjectName("aisFtr")
        ftr.setFixedHeight(56)
        ftr.setStyleSheet("QFrame#aisFtr { background: #252526; border: none; border-top: 1px solid #2a2a2a; }")
        ftr_l = QHBoxLayout(ftr)
        ftr_l.setContentsMargins(20, 0, 20, 0)
        ftr_l.setSpacing(8)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setStyleSheet("""
            QPushButton { background: #2d2d2d; color: #aaaaaa; border: 1px solid #3d3d3d; border-radius: 5px; font-size: 12px; padding: 0 20px; }
            QPushButton:hover { border-color: #4CAF50; color: #ffffff; }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        ftr_l.addWidget(cancel_btn)
        ftr_l.addStretch()
        save_btn = QPushButton("  Save")
        save_btn.setIcon(qta.icon('fa5s.check', color='#ffffff'))
        save_btn.setFixedHeight(34)
        save_btn.setStyleSheet("""
            QPushButton { background: #4CAF50; color: #fff; border: none; border-radius: 5px; font-size: 12px; font-weight: bold; padding: 0 24px; }
            QPushButton:hover { background: #45a049; }
            QPushButton:pressed { background: #3d8b40; }
        """)
        save_btn.clicked.connect(dialog.accept)
        ftr_l.addWidget(save_btn)
        root.addWidget(ftr)
        
        # Show dialog and save settings if accepted
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.import_format_type = format_combo.currentText()
            
            delim_text = delimiter_combo.currentText()
            if "Comma" in delim_text:
                self.import_delimiter = ","
            elif "Semicolon" in delim_text:
                self.import_delimiter = ";"
            elif "Tab" in delim_text:
                self.import_delimiter = "\t"
            elif "Pipe" in delim_text:
                self.import_delimiter = "|"
            
            self.import_has_header = has_header_check.isChecked()
            
            self.add_activity(f"✓ Import settings updated: {self.import_format_type}, Delimiter: {repr(self.import_delimiter)}, Headers: {self.import_has_header}")
    

    def preview_import_file(self, file_path):
        """Preview the import file content in table"""
        try:
            # Reset to default columns for CSV/JSON
            self.import_preview_table.setColumnCount(10)
            self.import_preview_table.setHorizontalHeaderLabels(["UID", "Name", "Email", "Phone", "Password", "Birthday", "Gender", "Device", "Status", "Notes"])
            self.import_preview_table.setRowCount(0)
            
            if file_path.endswith('.csv'):
                import csv
                
                # Use stored delimiter setting
                delimiter = self.import_delimiter
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    rows = list(reader)
                    
                    # Use stored header setting
                    start_row = 1 if self.import_has_header and len(rows) > 0 else 0
                    
                    # Show first 10 rows
                    for i, row in enumerate(rows[start_row:start_row+10]):
                        self.import_preview_table.insertRow(i)
                        for col, value in enumerate(row[:10]):  # Max 10 columns
                            item = QTableWidgetItem(value)
                            self.import_preview_table.setItem(i, col, item)
                    
            elif file_path.endswith('.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                accounts = []
                if isinstance(data, list):
                    accounts = data[:10]  # First 10
                elif isinstance(data, dict):
                    if 'accounts' in data:
                        accounts = data['accounts'][:10]
                    else:
                        accounts = [data]
                
                for i, account in enumerate(accounts):
                    self.import_preview_table.insertRow(i)
                    cols = ['uid', 'name', 'email', 'phone', 'password', 'birthday', 'gender', 'device', 'status', 'notes']
                    for col_idx, col_name in enumerate(cols):
                        value = str(account.get(col_name, ''))
                        item = QTableWidgetItem(value)
                        self.import_preview_table.setItem(i, col_idx, item)
            
            self.preview_info_label.setText(f"Showing preview (first 10 rows)")
                        
        except Exception as e:
            self.validation_label.setText(f"❌ Error previewing file: {str(e)}")
            self.validation_label.setStyleSheet("color: #f48771; font-size: 11px;")
    

    def validate_import_file(self):
        """Validate the import file or custom paste"""
        # Check if custom paste mode
        if hasattr(self, 'import_type_custom') and self.import_type_custom.isChecked():
            return self.validate_custom_paste()
        
        file_path = self.import_file_path.text()
        if not file_path or not os.path.exists(file_path):
            self.validation_label.setText("❌ Please select a file first")
            self.validation_label.setStyleSheet("color: #f48771; font-size: 11px;")
            return
        
        try:
            valid_count = 0
            invalid_count = 0
            total_count = 0
            
            if file_path.endswith('.csv'):
                import csv
                # Use stored delimiter setting
                delimiter = self.import_delimiter
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    rows = list(reader)
                    
                    # Use stored header setting
                    start_row = 1 if self.import_has_header and len(rows) > 0 else 0
                    
                    for row in rows[start_row:]:
                        total_count += 1
                        # Check if has at least email or phone
                        if len(row) >= 4 and (row[2] or row[3]):  # email or phone
                            valid_count += 1
                        else:
                            invalid_count += 1
                            
            elif file_path.endswith('.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                accounts = []
                if isinstance(data, list):
                    accounts = data
                elif isinstance(data, dict):
                    if 'accounts' in data:
                        accounts = data['accounts']
                    else:
                        accounts = [data]
                
                for account in accounts:
                    total_count += 1
                    if account.get('email') or account.get('phone'):
                        valid_count += 1
                    else:
                        invalid_count += 1
            
            # Update validation label
            if invalid_count == 0:
                self.validation_label.setText(f"✅ Validation passed: {valid_count} valid accounts found")
                self.validation_label.setStyleSheet("color: #89d185; font-size: 11px;")
                self.import_accounts_btn.setEnabled(True)
                self.import_stats_label.setText(f"{valid_count} accounts ready to import")
            else:
                self.validation_label.setText(f"⚠️ Found {valid_count} valid and {invalid_count} invalid accounts (missing email/phone)")
                self.validation_label.setStyleSheet("color: #cca700; font-size: 11px;")
                self.import_accounts_btn.setEnabled(True)
                self.import_stats_label.setText(f"{valid_count} accounts ready to import")
                
        except Exception as e:
            self.validation_label.setText(f"❌ Validation failed: {str(e)}")
            self.validation_label.setStyleSheet("color: #f48771; font-size: 11px;")
            self.import_accounts_btn.setEnabled(False)
    

    def clear_import_form(self):
        """Clear the import form"""
        self.import_file_path.clear()
        self.file_info_label.clear()
        self.import_preview_table.setRowCount(0)
        self.validation_label.clear()
        self.import_accounts_btn.setEnabled(False)
        self.import_stats_label.setText("Ready to import")
        if hasattr(self, 'import_custom_text'):
            self.import_custom_text.clear()
    

    def validate_custom_paste(self):
        """Validate custom pasted data"""
        text = self.import_custom_text.toPlainText().strip()
        if not text:
            self.validation_label.setText("❌ Please paste account data first")
            self.validation_label.setStyleSheet("color: #f48771; font-size: 11px;")
            return
        
        try:
            accounts = self.parse_custom_paste(text)
            valid_count = len(accounts)
            
            if valid_count == 0:
                self.validation_label.setText("❌ No valid accounts found in pasted data")
                self.validation_label.setStyleSheet("color: #f48771; font-size: 11px;")
                self.import_accounts_btn.setEnabled(False)
                return
            
            # Show preview
            self.import_preview_table.setColumnCount(8)
            self.import_preview_table.setHorizontalHeaderLabels(["UID", "Password", "Email", "Phone", "2FA", "Cookie", "Token", "Notes"])
            self.import_preview_table.setRowCount(0)
            
            for i, acc in enumerate(accounts[:10]):
                self.import_preview_table.insertRow(i)
                self.import_preview_table.setItem(i, 0, QTableWidgetItem(acc.get('uid', '')))
                self.import_preview_table.setItem(i, 1, QTableWidgetItem(acc.get('password', '')))
                self.import_preview_table.setItem(i, 2, QTableWidgetItem(acc.get('email', '')))
                self.import_preview_table.setItem(i, 3, QTableWidgetItem(acc.get('phone', '')))
                self.import_preview_table.setItem(i, 4, QTableWidgetItem(acc.get('2fa', '')))
                cookie_preview = acc.get('cookies', '')[:50] + '...' if len(acc.get('cookies', '')) > 50 else acc.get('cookies', '')
                self.import_preview_table.setItem(i, 5, QTableWidgetItem(cookie_preview))
                self.import_preview_table.setItem(i, 6, QTableWidgetItem(acc.get('token', '')))
                self.import_preview_table.setItem(i, 7, QTableWidgetItem(acc.get('notes', '')))
            
            self.preview_info_label.setText(f"Showing {min(valid_count, 10)} of {valid_count} accounts")
            self.validation_label.setText(f"✅ Validation passed: {valid_count} valid accounts found")
            self.validation_label.setStyleSheet("color: #89d185; font-size: 11px;")
            self.import_accounts_btn.setEnabled(True)
            self.import_stats_label.setText(f"{valid_count} accounts ready to import")
            
        except Exception as e:
            self.validation_label.setText(f"❌ Validation failed: {str(e)}")
            self.validation_label.setStyleSheet("color: #f48771; font-size: 11px;")
            self.import_accounts_btn.setEnabled(False)
    

    def parse_custom_paste(self, text):
        """
        Intelligent parser that analyzes the entire dataset to detect format.
        Uses pattern analysis and confidence scoring for accurate field detection.
        """
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        
        if not lines:
            return []
        
        # Step 1: Detect delimiter by analyzing all lines
        delimiter = self._detect_delimiter(lines)
        
        # Step 2: Split all lines into columns
        all_rows = [line.split(delimiter) for line in lines]
        
        # Step 3: Analyze each column across ALL rows to determine field type
        column_types = self._analyze_columns(all_rows)
        
        # Step 4: Map columns to account fields based on analysis
        accounts = []
        for row in all_rows:
            account = {}
            tokens = []  # Collect multiple tokens
            
            for col_idx, value in enumerate(row):
                value = value.strip()
                if not value:
                    continue
                
                field_type = column_types.get(col_idx, 'notes')
                
                # Double-check: if detected as token but looks like cookie, treat as cookie
                if field_type == 'token' and (value.startswith('c_user=') or value.startswith('xs=') or value.startswith('fr=') or value.startswith('datr=') or (';' in value and value.count(';') >= 2)):
                    field_type = 'cookie'
                
                # Double-check: if detected as cookie but looks like token, treat as token
                if field_type == 'cookie' and not (value.startswith('c_user=') or value.startswith('xs=') or value.startswith('fr=') or value.startswith('datr=') or ';' in value):
                    field_type = 'token'
                
                if field_type == 'uid':
                    account['uid'] = value
                elif field_type == 'password':
                    account['password'] = value
                elif field_type == 'email':
                    account['email'] = value
                elif field_type == 'phone':
                    account['phone'] = value
                elif field_type == '2fa':
                    account['2fa'] = value
                elif field_type == 'cookie':
                    account['cookies'] = value
                elif field_type == 'token':
                    tokens.append(value)  # Collect all tokens
                else:
                    # Add to notes
                    if 'notes' not in account:
                        account['notes'] = value
                    else:
                        account['notes'] += ' | ' + value
            
            # Combine tokens if multiple found
            if tokens:
                if len(tokens) == 1:
                    account['token'] = tokens[0]
                else:
                    # Multiple tokens: use longest as main token, others as notes
                    tokens_sorted = sorted(tokens, key=len, reverse=True)
                    account['token'] = tokens_sorted[0]
                    if 'notes' not in account:
                        account['notes'] = f"Additional tokens: {' | '.join(tokens_sorted[1:])}"
                    else:
                        account['notes'] += f" | Additional tokens: {' | '.join(tokens_sorted[1:])}"
            
            if account.get('uid') or account.get('email') or account.get('phone'):
                accounts.append(account)
        
        return accounts
    
    def _detect_delimiter(self, lines):
        """
        Intelligently detect the delimiter by analyzing all lines.
        Returns the most likely delimiter.
        """
        delimiters = ['|', '\t', ',', ';']
        scores = {}
        
        for delim in delimiters:
            # Count how many lines have this delimiter
            lines_with_delim = sum(1 for line in lines if delim in line)
            
            if lines_with_delim == 0:
                scores[delim] = 0
                continue
            
            # Check consistency: do all lines have similar number of delimiters?
            counts = [line.count(delim) for line in lines if delim in line]
            if not counts:
                scores[delim] = 0
                continue
            
            avg_count = sum(counts) / len(counts)
            consistency = 1.0 - (max(counts) - min(counts)) / (avg_count + 1)
            
            # Score = coverage * consistency * average_fields
            coverage = lines_with_delim / len(lines)
            scores[delim] = coverage * consistency * avg_count
        
        # Return delimiter with highest score
        best_delim = max(scores.items(), key=lambda x: x[1])[0]
        return best_delim
    
    def _analyze_columns(self, all_rows):
        """
        Analyze each column across all rows to determine field type.
        Uses confidence scoring for intelligent detection.
        """
        if not all_rows:
            return {}
        
        # Find max columns
        max_cols = max(len(row) for row in all_rows)
        column_types = {}
        
        for col_idx in range(max_cols):
            # Extract all values in this column
            column_values = []
            for row in all_rows:
                if col_idx < len(row):
                    val = row[col_idx].strip()
                    if val:
                        column_values.append(val)
            
            if not column_values:
                continue
            
            # Analyze this column to determine field type
            field_type = self._detect_field_type(column_values, col_idx)
            column_types[col_idx] = field_type
        
        return column_types
    
    def _detect_field_type(self, values, col_idx):
        """
        Detect field type for a column by analyzing all its values.
        Returns the most likely field type with confidence scoring.
        """
        if not values:
            return 'notes'
        
        # Calculate confidence scores for each field type
        scores = {
            'uid': 0.0,
            'password': 0.0,
            'email': 0.0,
            'phone': 0.0,
            '2fa': 0.0,
            'cookie': 0.0,
            'token': 0.0,
            'notes': 0.0
        }
        
        total = len(values)
        
        # UID Detection
        uid_matches = sum(1 for v in values if v.isdigit() and 10 <= len(v) <= 20)
        scores['uid'] = uid_matches / total
        
        # Email Detection
        email_matches = sum(1 for v in values if '@' in v and '.' in v and '=' not in v)
        scores['email'] = email_matches / total
        
        # Phone Detection
        phone_matches = sum(1 for v in values 
                           if (v.startswith('+') or v.replace('-', '').replace(' ', '').isdigit()) 
                           and 10 <= len(v.replace('-', '').replace(' ', '').replace('+', '')) <= 15)
        scores['phone'] = phone_matches / total
        
        # Cookie Detection (starts with c_user= OR has multiple key=value pairs with semicolons)
        cookie_matches = sum(1 for v in values 
                            if v.startswith('c_user=')  # Facebook cookie format
                            or v.startswith('xs=')  # Cookie component
                            or v.startswith('fr=')  # Cookie component
                            or v.startswith('datr=')  # Cookie component
                            or (';' in v and '=' in v and v.count(';') >= 2))  # Multiple key=value pairs
        scores['cookie'] = cookie_matches / total
        
        # Boost cookie score significantly to ensure it wins over token
        if scores['cookie'] > 0.5:
            scores['cookie'] *= 2.0
        
        # 2FA Detection (short alphanumeric code, 8-40 chars, NOT cookie, NOT token with special chars)
        twofa_matches = sum(1 for v in values 
                           if 8 <= len(v) <= 40 
                           and v.replace('-', '').replace('_', '').isalnum()  # Only alphanumeric (and - _)
                           and any(c.isalpha() for c in v)  # Has letters
                           and any(c.isdigit() for c in v)  # Has digits
                           and '=' not in v  # NOT a cookie
                           and ';' not in v  # NOT a cookie
                           and '*' not in v  # NOT a token with special chars
                           and '!' not in v  # NOT a token with special chars
                           and '$' not in v)  # NOT a token with special chars
        scores['2fa'] = twofa_matches / total
        
        # Token Detection (very long alphanumeric, >50 chars, NOT cookie format)
        # Also check for tokens with special chars like * ! $ . _
        # MUST NOT start with c_user= and MUST NOT have semicolons in first 50 chars
        token_matches = sum(1 for v in values 
                           if len(v) > 50 
                           and not v.startswith('c_user=')  # NOT a cookie
                           and not v.startswith('xs=')  # NOT a cookie
                           and not v.startswith('fr=')  # NOT a cookie
                           and not v.startswith('datr=')  # NOT a cookie
                           and ';' not in v[:100])  # No semicolon in first 100 chars (cookies have early semicolons)
        scores['token'] = token_matches / total
        
        # Password Detection (mixed characters, 6-30 chars, not matching other patterns)
        password_matches = sum(1 for v in values 
                              if 6 <= len(v) <= 30
                              and not v.isdigit()
                              and '@' not in v
                              and '=' not in v
                              and ';' not in v
                              and not (v.replace('-', '').replace('_', '').isalnum() and v.isupper()))
        scores['password'] = password_matches / total
        
        # Position-based boosting for common formats
        if col_idx == 0:
            scores['uid'] *= 2.0
        elif col_idx == 1:
            scores['password'] *= 1.5
        elif col_idx == 2:
            # Column 2 might be empty, username, or notes
            pass
        elif col_idx == 3:
            # Column 3 often email
            scores['email'] *= 1.4
        elif col_idx == 4:
            # Column 4 often 2FA (short code)
            scores['2fa'] *= 1.5
        elif col_idx == 5:
            # Column 5 often long access token
            scores['token'] *= 1.4
        elif col_idx == 6:
            # Column 6 could be another token (UUID) or device ID
            # Check if it looks like UUID format
            if values and any('-' in v and len(v) == 36 for v in values[:5]):
                # Looks like UUID, treat as secondary token
                scores['token'] *= 1.2
            else:
                scores['cookie'] *= 1.2
        elif col_idx == 7:
            # Column 7 often cookie
            scores['cookie'] *= 1.6
        
        # Find field type with highest confidence
        best_type = max(scores.items(), key=lambda x: x[1])
        
        # Only return if confidence is above threshold (30%)
        if best_type[1] >= 0.3:
            return best_type[0]
        else:
            return 'notes'
    

    def import_from_custom_paste(self):
        """Import accounts from custom pasted data"""
        import time as time_module
        from datetime import datetime
        import subprocess
        import tempfile
        
        text = self.import_custom_text.toPlainText().strip()
        if not text:
            return 0
        
        accounts = self.parse_custom_paste(text)
        if not accounts:
            return 0
        
        imported_count = 0
        backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")
        
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder)
        
        # Grant permissions to backup folder (Windows fix)
        username = os.environ.get('USERNAME', 'Everyone')
        try:
            subprocess.run(
                ['icacls', backup_folder, '/grant', f'{username}:F', '/t', '/c'],
                capture_output=True, text=True, timeout=5, 
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except:
            pass
        
        for account_data in accounts:
            uid = account_data.get('uid', '')
            email = account_data.get('email', '')
            phone = account_data.get('phone', '')
            password = account_data.get('password', '')
            twofa = account_data.get('2fa', '')
            cookies = account_data.get('cookies', '')
            token = account_data.get('token', '')
            notes = account_data.get('notes', '')
            
            # Create unique account folder with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
            
            if uid:
                folder_name = f"{uid}_{timestamp}"
            elif email:
                safe_email = email.replace('@', '_at_').replace('.', '_')
                folder_name = f"{safe_email}_{timestamp}"
            elif phone:
                folder_name = f"{phone}_{timestamp}"
            else:
                continue
            
            account_folder = os.path.join(backup_folder, folder_name)
            
            try:
                # Method 1: Direct write
                try:
                    os.makedirs(account_folder, exist_ok=True)
                    
                    # Grant permissions immediately
                    try:
                        subprocess.run(
                            ['icacls', account_folder, '/grant', f'{username}:F', '/c'],
                            capture_output=True, text=True, timeout=2,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                    except:
                        pass
                    
                    account_info = {
                        'account_uid': uid,
                        'email': email,
                        'phone': phone,
                        'password': password,
                        '2fa': twofa,
                        'twofa': twofa,
                        'cookies': cookies,
                        'token': token,
                        'device_info': {'model': 'Custom Import', 'device_name_short': 'N/A'},
                        'status': 'active',
                        'notes': notes or 'Imported from custom paste',
                        'imported': True,
                        'created_at': time_module.strftime('%Y-%m-%d %H:%M:%S'),
                        'import_date': time_module.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    info_file = os.path.join(account_folder, 'account_info.json')
                    
                    with open(info_file, 'w', encoding='utf-8') as f:
                        json.dump(account_info, f, indent=4)
                    
                    imported_count += 1
                    self.add_activity(f"✓ {uid or email or phone}")
                    
                except PermissionError:
                    # Method 2: Write to temp first, then move
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as tmp_file:
                        account_info = {
                            'account_uid': uid,
                            'email': email,
                            'phone': phone,
                            'password': password,
                            '2fa': twofa,
                            'twofa': twofa,
                            'cookies': cookies,
                            'token': token,
                            'device_info': {'model': 'Custom Import', 'device_name_short': 'N/A'},
                            'status': 'active',
                            'notes': notes or 'Imported from custom paste',
                            'imported': True,
                            'created_at': time_module.strftime('%Y-%m-%d %H:%M:%S'),
                            'import_date': time_module.strftime('%Y-%m-%d %H:%M:%S')
                        }
                        json.dump(account_info, tmp_file, indent=4)
                        tmp_path = tmp_file.name
                    
                    # Try to move temp file to destination
                    try:
                        os.makedirs(account_folder, exist_ok=True)
                        dest_file = os.path.join(account_folder, 'account_info.json')
                        shutil.move(tmp_path, dest_file)
                        imported_count += 1
                        self.add_activity(f"✓ {uid or email or phone}")
                    except:
                        # Cleanup temp file
                        try:
                            os.remove(tmp_path)
                        except:
                            pass
                        raise
                        
            except Exception as e:
                self.add_activity(f"⚠️  {uid or email or phone}: {str(e)[:50]}")
                continue
        
        return imported_count
    

    def clear_import_form(self):
        """Clear the import form"""
        self.import_file_path.clear()
        self.file_info_label.clear()
        self.import_preview_table.setRowCount(0)
        self.validation_label.clear()
        self.import_accounts_btn.setEnabled(False)
        self.import_stats_label.setText("Ready to import")
    

    def import_accounts(self):
        """Import accounts from file, TAR folder, or custom paste"""
        # Check if custom paste mode
        if hasattr(self, 'import_type_custom') and self.import_type_custom.isChecked():
            text = self.import_custom_text.toPlainText().strip()
            if not text:
                QMessageBox.warning(self, "No Data", "Please paste account data first!")
                return
            
            try:
                imported_count = self.import_from_custom_paste()
                
                if imported_count > 0:
                    QMessageBox.information(self, "Success", f"Successfully imported {imported_count} accounts!")
                    self.add_activity(f"✅ Imported {imported_count} accounts from custom paste")
                    
                    # Refresh account tab if open
                    if hasattr(self, 'account_table'):
                        self.load_main_account_tab()
                    
                    # Update dashboard statistics
                    if hasattr(self, 'total_accounts'):
                        _ab = os.path.join(_PROJECT_ROOT, "account_backup")
                        self.total_accounts = len([f for f in os.listdir(_ab)
                                                   if os.path.isdir(os.path.join(_ab, f))]) \
                                             if os.path.exists(_ab) else 0
                        if hasattr(self, 'update_statistics_display'):
                            self.update_statistics_display()
                    
                    # Clear form
                    self.clear_import_form()
                else:
                    QMessageBox.warning(self, "No Data", "No accounts were imported. Please check the format.")
                    
            except Exception as e:
                QMessageBox.critical(self, "Import Failed", f"Failed to import accounts:\n{str(e)}")
                self.add_activity(f"❌ Import failed: {str(e)}")
            return
        
        # Original file/folder import logic
        file_path = self.import_file_path.text()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "No Selection", "Please select a file or folder to import!")
            return
        
        try:
            imported_count = 0
            
            # Check if it's a folder (TAR/account folder mode)
            if os.path.isdir(file_path):
                imported_count = self.import_from_tar_folder(file_path)
            elif file_path.endswith('.csv'):
                imported_count = self.import_from_csv(file_path)
            elif file_path.endswith('.json'):
                imported_count = self.import_from_json(file_path)
            else:
                QMessageBox.warning(self, "Unsupported Format", "Please select a CSV/JSON file or folder with TAR archives!")
                return
            
            if imported_count > 0:
                QMessageBox.information(self, "Success", f"Successfully imported {imported_count} accounts!")
                self.add_activity(f"✅ Imported {imported_count} accounts")
                
                # Refresh account tab if open
                if hasattr(self, 'account_table'):
                    self.load_main_account_tab()
                
                # Update dashboard statistics
                if hasattr(self, 'total_accounts'):
                    _ab = os.path.join(_PROJECT_ROOT, "account_backup")
                    self.total_accounts = len([f for f in os.listdir(_ab)
                                               if os.path.isdir(os.path.join(_ab, f))]) \
                                         if os.path.exists(_ab) else 0
                    if hasattr(self, 'update_statistics_display'):
                        self.update_statistics_display()
                
                # Clear form
                self.clear_import_form()
            else:
                QMessageBox.warning(self, "No Data", "No accounts were imported. Please check the file/folder format.")
                
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Failed to import accounts:\n{str(e)}")
            self.add_activity(f"❌ Import failed: {str(e)}")
    

    def import_from_csv(self, file_path):
        """Import accounts from CSV file"""
        import csv
        imported_count = 0
        backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")
        
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder)
        
        # Use stored delimiter setting
        delimiter = self.import_delimiter
        
        with open(file_path, 'r', encoding='utf-8') as f:
            if self.import_has_header:
                reader = csv.DictReader(f, delimiter=delimiter)
            else:
                # No header, use default column names
                reader = csv.DictReader(f, delimiter=delimiter, fieldnames=[
                    'UID', 'Name', 'Email', 'Phone', 'Password', 'Birthday', 'Gender', 'Device', 'Status', 'Notes'
                ])
            
            for row in reader:
                try:
                    # Extract data from CSV
                    uid = row.get('UID', '')
                    name = row.get('Name', '')
                    email = row.get('Email', '')
                    phone = row.get('Phone', '')
                    password = row.get('Password', '')
                    birthday = row.get('Birthday', '')
                    gender = row.get('Gender', '')
                    device = row.get('Device', '')
                    status = row.get('Status', 'Imported')
                    notes = row.get('Notes', '')
                    
                    # Skip if no identifier
                    if not uid and not email and not phone:
                        continue
                    
                    # Create account folder
                    if uid:
                        account_folder = os.path.join(backup_folder, f"account_{uid}")
                    elif email:
                        account_folder = os.path.join(backup_folder, f"account_{email.replace('@', '_at_')}")
                    elif phone:
                        account_folder = os.path.join(backup_folder, f"account_{phone}")
                    else:
                        continue
                    
                    if not os.path.exists(account_folder):
                        os.makedirs(account_folder)
                    
                    # Save account info
                    account_info = {
                        'account_uid': uid,
                        'full_name': name,
                        'email': email,
                        'phone': phone,
                        'password': password,
                        'birthday': birthday,
                        'gender': gender,
                        'device_info': {'model': device or 'Imported', 'device_name_short': 'N/A'},
                        'status': status or 'active',
                        'notes': notes,
                        'imported': True,
                        'created_at': time_module.strftime('%Y-%m-%d %H:%M:%S'),
                        'import_date': time_module.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    info_file = os.path.join(account_folder, 'account_info.json')
                    with open(info_file, 'w', encoding='utf-8') as info_f:
                        json.dump(account_info, info_f, indent=4)
                    
                    imported_count += 1
                    
                except Exception as e:
                    print(f"Error importing row: {e}")
                    continue
        
        return imported_count
    

    def import_from_json(self, file_path):
        """Import accounts from JSON file"""
        imported_count = 0
        backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")
        
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different JSON structures
        accounts = []
        if isinstance(data, list):
            accounts = data
        elif isinstance(data, dict):
            if 'accounts' in data:
                accounts = data['accounts']
            else:
                accounts = [data]  # Single account
        
        for account in accounts:
            try:
                uid = account.get('uid', '')
                name = account.get('name', '')
                email = account.get('email', '')
                phone = account.get('phone', '')
                password = account.get('password', '')
                birthday = account.get('birthday', '')
                gender = account.get('gender', '')
                device = account.get('device', '')
                status = account.get('status', 'Imported')
                notes = account.get('notes', '')
                
                # Create account folder
                if uid:
                    account_folder = os.path.join(backup_folder, f"account_{uid}")
                elif email:
                    account_folder = os.path.join(backup_folder, f"account_{email.replace('@', '_at_')}")
                elif phone:
                    account_folder = os.path.join(backup_folder, f"account_{phone}")
                else:
                    continue
                
                if not os.path.exists(account_folder):
                    os.makedirs(account_folder)
                
                # Save account info
                account_info = {
                    'account_uid': uid,
                    'full_name': name,
                    'email': email,
                    'phone': phone,
                    'password': password,
                    'birthday': birthday,
                    'gender': gender,
                    'device_info': {'model': device or 'Imported', 'device_name_short': 'N/A'},
                    'status': status or 'active',
                    'notes': notes,
                    'imported': True,
                    'created_at': time_module.strftime('%Y-%m-%d %H:%M:%S'),
                    'import_date': time_module.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                info_file = os.path.join(account_folder, 'account_info.json')
                with open(info_file, 'w', encoding='utf-8') as info_f:
                    json.dump(account_info, info_f, indent=4)
                
                imported_count += 1
                
            except Exception as e:
                print(f"Error importing account: {e}")
                continue
        
        return imported_count
    

    def _extract_profile_db(self, acc_folder, uid_value):
        """Extract name, birthday from contacts DB inside Profile info tar.gz"""
        import tarfile, sqlite3, tempfile, shutil, json as _json

        profile_subfolder = os.path.join(acc_folder, 'Profile info')
        if not os.path.exists(profile_subfolder):
            return {}

        for fname in os.listdir(profile_subfolder):
            if uid_value in fname and fname.endswith(('.tar.gz', '.tgz', '.tar')):
                tar_path = os.path.join(profile_subfolder, fname)
                tmp = tempfile.mkdtemp()
                try:
                    with tarfile.open(tar_path, 'r:*') as tar:
                        # Only extract the contacts DB - avoid extracting everything
                        contacts_members = [m for m in tar.getmembers()
                                            if 'contacts_db' in m.name
                                            and not m.name.endswith('-journal')
                                            and not m.name.endswith('-wal')
                                            and not m.name.endswith('-shm')]
                        if contacts_members:
                            tar.extract(contacts_members[0], tmp)
                            db_path = os.path.join(tmp, contacts_members[0].name)
                            conn = sqlite3.connect(db_path)
                            cur = conn.cursor()
                            # Find the account owner row (fbid matches uid)
                            cur.execute(
                                "SELECT first_name, last_name, display_name, bday_day, bday_month, data "
                                "FROM contacts WHERE fbid=? LIMIT 1", (uid_value,)
                            )
                            row = cur.fetchone()
                            conn.close()
                            if row:
                                first_name, last_name, display_name, bday_day, bday_month, data_json = row
                                result = {
                                    'full_name': display_name or f"{first_name} {last_name}".strip(),
                                    'first_name': first_name or '',
                                    'last_name': last_name or '',
                                }
                                # Build birthday string
                                if bday_day and bday_month:
                                    result['birthday'] = f"{bday_month:02d}/{bday_day:02d}"
                                # Try to get gender from data JSON
                                if data_json:
                                    try:
                                        d = _json.loads(data_json)
                                        gender_raw = d.get('gender', '')
                                        if gender_raw:
                                            result['gender'] = gender_raw.capitalize()
                                    except Exception:
                                        pass
                                return result
                except Exception as e:
                    print(f"Error reading profile DB: {e}")
                finally:
                    try:
                        shutil.rmtree(tmp, ignore_errors=True)
                    except Exception:
                        pass
        return {}


    def _extract_device_xml(self, acc_folder, uid_value):
        """Extract Device.xml from Device info tar.gz and return parsed data"""
        import tarfile
        import xml.etree.ElementTree as ET

        device_subfolder = os.path.join(acc_folder, 'Device info')
        if not os.path.exists(device_subfolder):
            return {}

        # Find the tar.gz matching this uid
        for fname in os.listdir(device_subfolder):
            if uid_value in fname and fname.endswith(('.tar.gz', '.tgz', '.tar')):
                tar_path = os.path.join(device_subfolder, fname)
                try:
                    with tarfile.open(tar_path, 'r:*') as tar:
                        # Find Device.xml inside
                        for member in tar.getmembers():
                            if member.name.endswith('Device.xml'):
                                f = tar.extractfile(member)
                                if f:
                                    xml_content = f.read().decode('utf-8', errors='ignore')
                                    root = ET.fromstring(xml_content)
                                    data = {}
                                    for elem in root:
                                        name = elem.get('name', '')
                                        value = elem.get('value') or elem.text or ''
                                        data[name] = value
                                    return data
                except Exception as e:
                    print(f"Error reading Device.xml: {e}")
        return {}


    def import_from_tar_folder(self, folder_path):
        """Import accounts from folder structure (supports pipe-delimited and Key:Value Acc info)"""
        import tarfile
        import shutil
        from datetime import datetime

        imported_count = 0
        failed_count = 0
        backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")

        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder)

        account_folders = self._find_account_folders(folder_path)

        if not account_folders:
            return 0

        self.add_activity(f"📦 Processing {len(account_folders)} folder(s)...")

        for acc_folder in account_folders:
            folder_name = os.path.basename(acc_folder)
            try:
                # Grant permissions to source folder first (Windows fix) - reduced timeout
                import subprocess
                import time
                username = os.environ.get('USERNAME', 'Everyone')
                try:
                    subprocess.run(['icacls', acc_folder, '/grant', f'{username}:F', '/t', '/c'], 
                                 capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                except:
                    pass  # Continue even if icacls fails
                
                # Find Acc info file
                acc_info_path = None
                for fname in os.listdir(acc_folder):
                    if fname.lower() in ('acc info', 'acc info.txt'):
                        acc_info_path = os.path.join(acc_folder, fname)
                        break

                if not acc_info_path:
                    self.add_activity(f"  ⚠️  {folder_name}: No 'Acc info' file found")
                    failed_count += 1
                    continue

                accounts = self._parse_acc_info(acc_info_path)

                if not accounts:
                    self.add_activity(f"  ⚠️  {folder_name}: Could not parse account data")
                    failed_count += 1
                    continue

                for account_data in accounts:
                    uid_value = account_data.get('uid', '') or folder_name
                    password = account_data.get('password', '')
                    cookies = account_data.get('cookies', '')

                    # Extract device info from Device.xml inside the tar.gz
                    dev = self._extract_device_xml(acc_folder, uid_value)

                    # Extract name/birthday/gender from Profile info contacts DB
                    profile = self._extract_profile_db(acc_folder, uid_value)

                    # Build rich account info from Device.xml
                    device_model = dev.get('model', dev.get('deviceName', 'Unknown'))
                    device_name = dev.get('deviceName', dev.get('product', device_model))
                    manufacturer = dev.get('manufacturer', '')
                    imei = dev.get('imei', '')
                    sim_phone = dev.get('phone_num', '')
                    android_id = dev.get('android_id', '')
                    serial = dev.get('serial', '')
                    android_version = dev.get('release', '')
                    country = dev.get('country', '')
                    sim_operator = dev.get('simOperatorName', '')
                    wifi_mac = dev.get('wifimac', '')
                    bt_mac = dev.get('bluetooth_mac', '')
                    latitude = dev.get('latitude', '')
                    longitude = dev.get('longitude', '')
                    fingerprint = dev.get('fingerprint', '')
                    user_agent = dev.get('user_agent', dev.get('http_agent', ''))

                    # Create destination account folder
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
                    dest_folder = os.path.join(backup_folder, f"{uid_value}_{timestamp}")
                    
                    # Grant permissions to backup folder first (Windows fix) - only once
                    if not hasattr(self, '_backup_folder_permissions_granted'):
                        try:
                            subprocess.run(['icacls', backup_folder, '/grant', f'{username}:F', '/t', '/c'], 
                                         capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                            self._backup_folder_permissions_granted = True
                        except:
                            pass
                    
                    os.makedirs(dest_folder, exist_ok=True)
                    
                    # Grant full permissions to the newly created folder immediately
                    try:
                        subprocess.run(['icacls', dest_folder, '/grant', f'{username}:F', '/c'], 
                                     capture_output=True, text=True, timeout=2, creationflags=subprocess.CREATE_NO_WINDOW)
                    except:
                        pass

                    # Copy Device info and Profile info tar.gz files (keep originals)
                    for subfolder_name in ('Device info', 'Profile info'):
                        src_subfolder = os.path.join(acc_folder, subfolder_name)
                        if os.path.exists(src_subfolder):
                            dst_subfolder = os.path.join(dest_folder, subfolder_name)
                            
                            # Create subfolder and immediately grant permissions
                            try:
                                os.makedirs(dst_subfolder, exist_ok=True)
                                subprocess.run(['icacls', dst_subfolder, '/grant', f'{username}:F', '/c'], 
                                             capture_output=True, text=True, timeout=2, creationflags=subprocess.CREATE_NO_WINDOW)
                            except Exception as mkdir_err:
                                self.add_activity(f"  ⚠️  Failed to create {subfolder_name}: {mkdir_err}")
                                continue
                            
                            for fname in os.listdir(src_subfolder):
                                if uid_value in fname:
                                    src_file = os.path.join(src_subfolder, fname)
                                    dst_file = os.path.join(dst_subfolder, fname)
                                    
                                    # Simple copy without excessive permission checks
                                    try:
                                        shutil.copy2(src_file, dst_file)
                                    except PermissionError:
                                        # Only if permission error, try PowerShell
                                        ps_cmd = f'Copy-Item -Path "{src_file}" -Destination "{dst_file}" -Force'
                                        subprocess.run(['powershell', '-Command', ps_cmd], 
                                                     capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)

                    # Save full account_info.json
                    account_json = {
                        "account_uid": uid_value,
                        "full_name": profile.get('full_name', ''),
                        "first_name": profile.get('first_name', ''),
                        "last_name": profile.get('last_name', ''),
                        "email": "",
                        "phone": sim_phone,
                        "password": password,
                        "birthday": profile.get('birthday', ''),
                        "gender": profile.get('gender', ''),
                        "cookies": cookies,
                        "device_info": {
                            "model": device_model,
                            "device_name_short": device_name,
                            "manufacturer": manufacturer,
                            "android_version": android_version,
                            "imei": imei,
                            "android_id": android_id,
                            "serial": serial,
                            "fingerprint": fingerprint,
                            "wifi_mac": wifi_mac,
                            "bluetooth_mac": bt_mac,
                            "country": country,
                            "sim_operator": sim_operator,
                            "latitude": latitude,
                            "longitude": longitude,
                            "user_agent": user_agent,
                        },
                        "status": "active",
                        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "imported": True,
                        "import_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "notes": f"Imported from {folder_name}"
                    }

                    with open(os.path.join(dest_folder, "account_info.json"), 'w', encoding='utf-8') as f:
                        json.dump(account_json, f, indent=4)

                    # Copy original Acc info file - simple approach
                    acc_info_dest = os.path.join(dest_folder, "Acc info")
                    try:
                        shutil.copy2(acc_info_path, acc_info_dest)
                    except PermissionError:
                        # Only if permission error, try PowerShell
                        ps_cmd = f'Copy-Item -Path "{acc_info_path}" -Destination "{acc_info_dest}" -Force'
                        subprocess.run(['powershell', '-Command', ps_cmd], 
                                     capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)

                    self.add_activity(f"  ✅ {profile.get('full_name', uid_value)} | {device_name} | {country.upper()}")
                    imported_count += 1

            except Exception as e:
                self.add_activity(f"  ❌ {folder_name}: {str(e)}")
                failed_count += 1

        if failed_count > 0:
            self.add_activity(f"⚠️  {failed_count} folder(s) had errors")

        return imported_count
    

    def open_import_tab(self):
        """Open the import accounts tab"""
        # Check if tab already exists
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Import":
                self.tab_widget.setCurrentIndex(i)
                return
        
        if hasattr(self, 'main_import_tab') and self.main_import_tab:
            # Add the tab
            self.import_tab_index = self.tab_widget.addTab(self.main_import_tab, "Import")
            self.tab_widget.setCurrentIndex(self.import_tab_index)
            
            # Add close button
            close_btn = QPushButton("×")
            close_btn.setFixedSize(20, 20)
            close_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #888888;
                    border: none;
                    font-size: 18px;
                    font-weight: bold;
                    padding: 0px;
                }
                QPushButton:hover {
                    color: #ffffff;
                    background-color: #e81123;
                }
            """)
            close_btn.clicked.connect(lambda checked, w=self.main_import_tab: self.close_dynamic_tab_by_widget(w))
            self.tab_widget.tabBar().setTabButton(self.import_tab_index, QTabBar.ButtonPosition.RightSide, close_btn)
    

    def update_account_stats(self):
        """Update the stats label with current device counts"""
        if not hasattr(self, 'account_table') or not hasattr(self, 'stats_label'):
            return
        
        total = self.account_table.rowCount()
        
        # Check if it's the empty state message
        if total == 1:
            item = self.account_table.item(0, 0)
            if item and item.text().startswith("No devices"):
                total = 0
        
        if total == 0:
            self.stats_label.setText("0 devices")
        elif total == 1:
            self.stats_label.setText("1 device")
        else:
            self.stats_label.setText(f"{total} devices")
        
        # Count active accounts (accounts with status not containing "Failed" or "Error")
        active_count = 0
        for row in range(self.account_table.rowCount()):
            status_item = self.account_table.item(row, 9)  # Status column
            if status_item:
                status = status_item.text()
                if status and "Failed" not in status and "Error" not in status:
                    active_count += 1
        
        if hasattr(self, 'working_label'):
            self.working_label.setText(str(active_count))
        
        # Update total_accounts variable
        self.total_accounts = total
    
