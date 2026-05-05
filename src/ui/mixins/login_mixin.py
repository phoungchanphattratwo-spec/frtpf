"""
LoginMixin — Login Mixin methods.

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

import os, json, subprocess, threading, time, tempfile, re

from src.i18n.engine import (
    translate as _T, register_widget as _reg,
    _CURRENT_LANG, _get_khmer_font, _REGISTRY as _I18N_REGISTRY,
)
from src.i18n.translations import TRANSLATIONS
from src.ui.safe_combobox import SafeComboBox
from src.automation.url_normalizer import normalize_facebook_url, URL_TYPE_LABELS as _URL_TYPE_LABELS
from src.core.config import CONFIG_FILE

# Project root — 3 levels up from src/ui/mixins/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.core.subprocess_utils import safe_subprocess_run
# Lazy import — registration pulls in appium/selenium (300-700ms cold-start)
# Import only when a registration/login session actually starts

class LoginMixin:
    """Mixin — methods are injected into MainWindow via multiple inheritance."""

    def close_main_login_tab(self):
        """Close the main Login tab"""
        # Find the Login tab by name instead of using stored index
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Login":
                self.tab_widget.removeTab(i)
                self.login_tab_index = -1  # Mark as closed
                return
        # Config will be saved automatically when app closes
    

    def open_login_tab(self):
        """Open or restore the Login tab"""
        # Check if Login tab already exists
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Login":
                self.tab_widget.setCurrentIndex(i)
                return
        
        # If tab was closed, recreate it
        if hasattr(self, 'main_login_tab') and self.main_login_tab:
            # Re-add the tab
            self.login_tab_index = self.tab_widget.addTab(self.main_login_tab, "Login")
            self.tab_widget.setCurrentIndex(self.login_tab_index)
            
            # Re-add close button
            login_close_btn = QPushButton("×")
            login_close_btn.setFixedSize(20, 20)
            login_close_btn.setStyleSheet("""
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
            login_close_btn.clicked.connect(self.close_main_login_tab)
            self.tab_widget.tabBar().setTabButton(self.login_tab_index, QTabBar.ButtonPosition.RightSide, login_close_btn)
            # Config will be saved automatically when app closes
    

    def select_account_for_login(self):
        """Open dialog to select accounts for login queue"""
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        dialog.setFixedSize(1100, 620)
        dialog.setStyleSheet("QDialog { background: #1e1e1e; border: 1px solid #3d3d3d; }")
        
        # Main layout
        root = QVBoxLayout(dialog)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame(); hdr.setObjectName("salHdr"); hdr.setFixedHeight(52)
        hdr.setStyleSheet("QFrame#salHdr { background: #252526; border: none; border-bottom: 1px solid #2a2a2a; }")
        hdr_l = QHBoxLayout(hdr); hdr_l.setContentsMargins(20, 0, 12, 0); hdr_l.setSpacing(10)
        ico = QLabel(); ico.setPixmap(qta.icon('fa5s.users', color='#4CAF50').pixmap(14, 14))
        ico.setStyleSheet("background: transparent;"); hdr_l.addWidget(ico)
        ttl = QLabel("Select Accounts for Login")
        ttl.setStyleSheet("color: #cccccc; font-size: 13px; font-weight: bold; background: transparent;")
        hdr_l.addWidget(ttl); hdr_l.addStretch()
        x_btn = QPushButton(); x_btn.setFixedSize(32, 32)
        x_btn.setIcon(qta.icon('fa5s.times', color='#888888'))
        x_btn.setIconSize(QSize(12, 12))
        x_btn.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: #f44336; }")
        x_btn.clicked.connect(dialog.reject); hdr_l.addWidget(x_btn)
        root.addWidget(hdr)

        def _drag_press(e):
            if e.button() == Qt.MouseButton.LeftButton:
                dialog.drag_pos = e.globalPosition().toPoint() - dialog.frameGeometry().topLeft()
        def _drag_move(e):
            if e.buttons() == Qt.MouseButton.LeftButton and hasattr(dialog, 'drag_pos'):
                dialog.move(e.globalPosition().toPoint() - dialog.drag_pos)
        hdr.mousePressEvent = _drag_press
        hdr.mouseMoveEvent = _drag_move
        
        # Filter bar
        _combo_s = """
            QComboBox { background: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 4px;
                        padding: 0 10px; color: #cccccc; font-size: 12px; min-width: 120px; height: 30px; }
            QComboBox:hover { border-color: #4CAF50; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow { image: none; border-left: 4px solid transparent;
                border-right: 4px solid transparent; border-top: 5px solid #888; margin-right: 6px; }
            QComboBox QAbstractItemView { 
                background: #252526; border: 1px solid #3d3d3d;
                color: #cccccc; selection-background-color: #4CAF50; selection-color: #fff;
                max-height: 300px; position: absolute; }
        """
        _search_s = """
            QLineEdit { background: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 4px;
                        padding: 0 10px; color: #cccccc; font-size: 12px; height: 30px; min-width: 220px; }
            QLineEdit:focus { border-color: #4CAF50; }
        """
        _lbl_s = "color: #666666; font-size: 11px; font-weight: bold; background: transparent;"

        fbar = QWidget(); fbar.setStyleSheet("background: #1e1e1e;")
        fbar_l = QHBoxLayout(fbar); fbar_l.setContentsMargins(20, 12, 20, 8); fbar_l.setSpacing(10)
        cl = QLabel("Category:"); cl.setStyleSheet(_lbl_s); fbar_l.addWidget(cl)
        category_filter = SafeComboBox(); category_filter.addItems(["All", "Email", "Phone", "---"])
        for cat in self.load_custom_categories(): category_filter.addItem(cat)
        category_filter.setStyleSheet(_combo_s); fbar_l.addWidget(category_filter)
        fbar_l.addSpacing(8)
        sl = QLabel("Status:"); sl.setStyleSheet(_lbl_s); fbar_l.addWidget(sl)
        status_filter = SafeComboBox(); status_filter.addItems(["All", "Pending SMS", "Pending Email", "Active", "Suspended"])
        status_filter.setStyleSheet(_combo_s); fbar_l.addWidget(status_filter)
        fbar_l.addStretch()
        sch_l = QLabel("Search:"); sch_l.setStyleSheet(_lbl_s); fbar_l.addWidget(sch_l)
        search_input = QLineEdit(); search_input.setPlaceholderText("Search by name, email, phone...")
        search_input.setStyleSheet(_search_s); fbar_l.addWidget(search_input)
        root.addWidget(fbar)
        
        # Table
        _tbl_s = """
            QTableWidget { background: #1e1e1e; border: none; gridline-color: #2a2a2a;
                color: #cccccc; font-size: 12px; outline: none; }
            QTableWidget::item { padding: 0 10px; border: none; }
            QTableWidget::item:selected { background: #2a4a2a; color: #ffffff; }
            QTableWidget::item:selected:hover { background: #2a4a2a; }
            QHeaderView::section { background: #252526; color: #4CAF50; font-size: 11px; font-weight: bold;
                letter-spacing: 0.5px; padding: 0 10px; height: 34px;
                border: none; border-bottom: 2px solid #4CAF50; border-right: 1px solid #2a2a2a; }
        """
        _cb_style = """
            QCheckBox { background: transparent; }
            QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid #3d3d3d;
                border-radius: 3px; background: #2d2d2d; }
            QCheckBox::indicator:hover { border-color: #4CAF50; }
            QCheckBox::indicator:checked { background: #4CAF50; border-color: #4CAF50; }
        """

        account_select_table = QTableWidget()
        account_select_table.setColumnCount(9)
        account_select_table.setHorizontalHeaderLabels(["", "Name", "Email", "Phone", "Password", "Birthday", "Gender", "Status", "Category"])
        account_select_table.setStyleSheet(_tbl_s)
        account_select_table.verticalHeader().setVisible(False)
        account_select_table.verticalHeader().setDefaultSectionSize(38)
        account_select_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        account_select_table.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        account_select_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        account_select_table.setShowGrid(True)
        hdr_view = account_select_table.horizontalHeader()
        hdr_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr_view.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        hdr_view.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        hdr_view.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        hdr_view.setHighlightSections(False)
        account_select_table.setColumnWidth(0, 50)
        self.account_select_table_ref = account_select_table
        all_accounts_data = []

        # Create a signal to notify when loading is complete
        from PyQt6.QtCore import QObject, pyqtSignal
        class LoadSignal(QObject):
            loaded = pyqtSignal()
        load_signal = LoadSignal()

        # Show dialog immediately with loading indicator, load data in background
        loading_item = QTableWidgetItem("Loading accounts...")
        loading_item.setForeground(QColor("#888888"))
        account_select_table.insertRow(0)
        account_select_table.setItem(0, 1, loading_item)

        def populate_table(accounts_to_show):
            account_select_table.setRowCount(0)
            for account_data in accounts_to_show:
                row = account_select_table.rowCount()
                account_select_table.insertRow(row)
                cb = QCheckBox(); cb.setStyleSheet(_cb_style)
                def _make_handler(r):
                    def _h(checked):
                        account_select_table.blockSignals(True)
                        if checked:
                            account_select_table.selectRow(r)
                        else:
                            account_select_table.clearSelection()
                            for i in range(account_select_table.rowCount()):
                                if i != r:
                                    w = account_select_table.cellWidget(i, 0)
                                    if w:
                                        c = w.findChild(QCheckBox)
                                        if c and c.isChecked():
                                            account_select_table.selectRow(i)
                        account_select_table.blockSignals(False)
                    return _h
                cb.stateChanged.connect(_make_handler(row))
                cw = QWidget(); cw.setStyleSheet("background: transparent;")
                cwl = QHBoxLayout(cw); cwl.addWidget(cb)
                cwl.setAlignment(Qt.AlignmentFlag.AlignCenter); cwl.setContentsMargins(0,0,0,0)
                account_select_table.setCellWidget(row, 0, cw)
                account_select_table.setItem(row, 1, QTableWidgetItem(account_data.get('full_name', 'N/A')))
                account_select_table.setItem(row, 2, QTableWidgetItem(account_data.get('email', '')))
                account_select_table.setItem(row, 3, QTableWidgetItem(account_data.get('phone', '')))
                pw = QTableWidgetItem(account_data.get('password', ''))
                pw.setForeground(QColor("#FF9800")); account_select_table.setItem(row, 4, pw)
                account_select_table.setItem(row, 5, QTableWidgetItem(account_data.get('birthday', '')))
                gi = QTableWidgetItem(account_data.get('gender', ''))
                g = account_data.get('gender', '').lower()
                gi.setForeground(QColor("#2196F3" if g == 'male' else "#E91E63" if g == 'female' else "#888888"))
                account_select_table.setItem(row, 6, gi)
                st = account_data.get('status', 'unknown')
                si = QTableWidgetItem(st)
                si.setForeground(QColor("#4CAF50" if 'active' in st.lower() else "#FF9800" if 'pending' in st.lower() else "#f44336" if 'suspended' in st.lower() else "#888888"))
                account_select_table.setItem(row, 7, si)
                category = account_data.get('category', '—')
                cat_item = QTableWidgetItem(category)
                cat_item.setForeground(QColor("#4CAF50") if category != "—" else QColor("#888888"))
                account_select_table.setItem(row, 8, cat_item)
                account_select_table.item(row, 1).setData(Qt.ItemDataRole.UserRole, account_data)
        
        def apply_filters():
            category = category_filter.currentText()
            status = status_filter.currentText()
            search_text = search_input.text().lower().strip()
            filtered = []
            for acc in all_accounts_data:
                if category not in ("All", "---"):
                    if category == "Email" and acc.get('signup_method', 'email') != "email": continue
                    elif category == "Phone" and acc.get('signup_method', 'email') != "phone": continue
                    elif category not in ("Email", "Phone") and acc.get('category', '') != category: continue
                if status != "All":
                    s = acc.get('status', '')
                    if status == "Pending SMS" and "sms" not in s.lower(): continue
                    if status == "Pending Email" and "email" not in s.lower(): continue
                    if status == "Active" and s != "active": continue
                    if status == "Suspended" and s != "suspended": continue
                if search_text:
                    fields = [acc.get(k, '') for k in ('full_name','first_name','last_name','email','phone','password')]
                    if not any(search_text in str(f).lower() for f in fields): continue
                filtered.append(acc)
            populate_table(filtered)

        def _load_accounts():
            data = []
            backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")
            if os.path.exists(backup_folder):
                for folder in [f for f in os.listdir(backup_folder) if os.path.isdir(os.path.join(backup_folder, f))]:
                    json_file = os.path.join(backup_folder, folder, "account_info.json")
                    if os.path.exists(json_file):
                        try:
                            with open(json_file, 'r', encoding='utf-8-sig') as f:
                                data.append(json.load(f))
                        except Exception as e:
                            print(f"Error loading {json_file}: {e}")
            all_accounts_data.extend(data)
            # Emit signal to trigger filter on main thread
            load_signal.loaded.emit()
        
        # Connect signal to apply_filters
        load_signal.loaded.connect(apply_filters)

        import threading as _t
        _t.Thread(target=_load_accounts, daemon=True).start()

        category_filter.currentTextChanged.connect(apply_filters)
        status_filter.currentTextChanged.connect(apply_filters)
        search_input.textChanged.connect(apply_filters)
        # Don't call apply_filters() here - it will be called after data loads

        def on_selection_changed():
            for r in range(account_select_table.rowCount()):
                w = account_select_table.cellWidget(r, 0)
                if w:
                    c = w.findChild(QCheckBox)
                    if c:
                        c.blockSignals(True)
                        c.setChecked(any(account_select_table.item(r, col) and account_select_table.item(r, col).isSelected()
                                         for col in range(account_select_table.columnCount())))
                        c.blockSignals(False)
        account_select_table.itemSelectionChanged.connect(on_selection_changed)

        tbl_wrap = QWidget(); tbl_wrap.setStyleSheet("background: #1e1e1e;")
        tbl_wrap_l = QVBoxLayout(tbl_wrap); tbl_wrap_l.setContentsMargins(20, 0, 20, 0)
        tbl_wrap_l.addWidget(account_select_table)
        root.addWidget(tbl_wrap, 1)

        # Footer
        ftr = QFrame(); ftr.setObjectName("salFtr"); ftr.setFixedHeight(56)
        ftr.setStyleSheet("QFrame#salFtr { background: #252526; border: none; border-top: 1px solid #2a2a2a; }")
        ftr_l = QHBoxLayout(ftr); ftr_l.setContentsMargins(20, 0, 20, 0); ftr_l.setSpacing(10)
        sel_count_lbl = QLabel("0 selected")
        sel_count_lbl.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
        ftr_l.addWidget(sel_count_lbl)
        def _update_count():
            n = sum(1 for r in range(account_select_table.rowCount())
                    if (w := account_select_table.cellWidget(r, 0)) and (c := w.findChild(QCheckBox)) and c.isChecked())
            sel_count_lbl.setText(f"{n} selected")
        account_select_table.itemSelectionChanged.connect(_update_count)
        clear_btn = QPushButton("Clear Selection"); clear_btn.setFixedHeight(34)
        clear_btn.setStyleSheet("QPushButton { background: #252526; color: #aaaaaa; border: 1px solid #3d3d3d; border-radius: 4px; font-size: 12px; padding: 0 16px; } QPushButton:hover { border-color: #f44336; color: #f44336; }")
        def _clear_selection():
            account_select_table.clearSelection()
            for r in range(account_select_table.rowCount()):
                w = account_select_table.cellWidget(r, 0)
                if w:
                    c = w.findChild(QCheckBox)
                    if c:
                        c.blockSignals(True); c.setChecked(False); c.blockSignals(False)
            sel_count_lbl.setText("0 selected")
        clear_btn.clicked.connect(_clear_selection); ftr_l.addWidget(clear_btn)

        ftr_l.addStretch()
        cancel_btn = QPushButton("Cancel"); cancel_btn.setFixedHeight(34)
        cancel_btn.setStyleSheet("QPushButton { background: #252526; color: #aaaaaa; border: 1px solid #3d3d3d; border-radius: 4px; font-size: 12px; padding: 0 16px; } QPushButton:hover { border-color: #4CAF50; color: #fff; }")
        cancel_btn.clicked.connect(dialog.reject); ftr_l.addWidget(cancel_btn)
        add_btn = QPushButton("  Add Selected"); add_btn.setFixedHeight(34)
        add_btn.setIcon(qta.icon('fa5s.plus', color='#ffffff'))
        add_btn.setStyleSheet("QPushButton { background: #4CAF50; color: #fff; border: none; border-radius: 4px; font-size: 12px; font-weight: bold; padding: 0 16px; } QPushButton:hover { background: #45a049; } QPushButton:pressed { background: #3d8b40; }")
        add_btn.clicked.connect(lambda: self.add_accounts_to_login_queue(account_select_table, dialog))
        ftr_l.addWidget(add_btn)
        root.addWidget(ftr)

        dialog.exec()
    

    def add_accounts_to_login_queue(self, table, dialog):
        """Add selected accounts to login queue"""
        added_count = 0
        
        for row in range(table.rowCount()):
            checkbox_widget = table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    name_item = table.item(row, 1)
                    if name_item:
                        account_data = name_item.data(Qt.ItemDataRole.UserRole)
                        if account_data:
                            self.add_account_to_queue(account_data)
                            added_count += 1
        
        dialog.accept()
        QMessageBox.information(self, "Success", f"Added {added_count} account(s) to login queue!")
    

    def add_account_to_queue(self, account_data):
        """Add a single account to the login queue table"""
        row = self.login_queue_table.rowCount()
        self.login_queue_table.insertRow(row)

        # Col 0 — Name
        name = account_data.get('full_name') or f"{account_data.get('first_name','')} {account_data.get('last_name','')}".strip() or 'N/A'
        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.ItemDataRole.UserRole, account_data)
        self.login_queue_table.setItem(row, 0, name_item)

        # Col 1 — UID
        uid_item = QTableWidgetItem(account_data.get('uid', account_data.get('account_uid', '')))
        uid_item.setForeground(QColor("#888888"))
        self.login_queue_table.setItem(row, 1, uid_item)

        # Col 2 — Phone
        self.login_queue_table.setItem(row, 2, QTableWidgetItem(account_data.get('phone', '')))

        # Col 3 — Password
        pwd_item = QTableWidgetItem(account_data.get('password', ''))
        pwd_item.setForeground(QColor("#FF9800"))
        self.login_queue_table.setItem(row, 3, pwd_item)

        # Col 4 — Device Info (from backup)
        dev_info = account_data.get('device_info', {})
        device_str = dev_info.get('device_name_short') or account_data.get('device', 'Unknown')
        device_item = QTableWidgetItem(device_str)
        device_item.setForeground(QColor("#888888"))
        self.login_queue_table.setItem(row, 4, device_item)

        # Col 5 — Assigned To (will be filled during login)
        assigned_item = QTableWidgetItem("-")
        assigned_item.setForeground(QColor("#666666"))
        self.login_queue_table.setItem(row, 5, assigned_item)

        # Col 6 — Status
        status_item = QTableWidgetItem("Pending")
        status_item.setForeground(QColor("#888888"))
        self.login_queue_table.setItem(row, 6, status_item)

        # Col 7 — Date
        date_str = account_data.get('import_date', account_data.get('created_at', ''))[:10]
        date_item = QTableWidgetItem(date_str)
        date_item.setForeground(QColor("#555555"))
        self.login_queue_table.setItem(row, 7, date_item)

        # Update badge
        count = self.login_queue_table.rowCount()
        self.queue_count_badge.setText(f"{count} account{'s' if count != 1 else ''}")
        
        # Save queue
        self._save_login_queue()
    

    def remove_from_login_queue(self, row):
        """Remove account from login queue"""
        self.login_queue_table.removeRow(row)
        self._save_login_queue()
    

    def clear_login_queue(self):
        """Clear all accounts from login queue"""
        if self.login_queue_table.rowCount() == 0:
            return
        reply = QMessageBox.question(
            self, "Clear Queue",
            f"Clear all {self.login_queue_table.rowCount()} account(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.login_queue_table.setRowCount(0)
            if hasattr(self, 'queue_count_label'):
                self.queue_count_label.setText("0 accounts in queue")
            self.login_status_label.setText("Queue cleared")
            self.login_status_label.setStyleSheet("color: #4CAF50; font-size: 10px; background: transparent;")
            self._save_login_queue()
    

    def _save_login_queue(self):
        """Save login queue to file"""
        # Skip saving during bulk load
        if getattr(self, '_loading_queue', False):
            return
        
        try:
            queue_data = []
            for row in range(self.login_queue_table.rowCount()):
                name_item = self.login_queue_table.item(row, 0)
                if name_item:
                    account_data = name_item.data(Qt.ItemDataRole.UserRole)
                    if account_data:
                        queue_data.append(account_data)
            
            queue_file = os.path.join(tempfile.gettempdir(), "frt_login_queue.json")
            with open(queue_file, 'w', encoding='utf-8') as f:
                json.dump(queue_data, f, indent=2)
        except Exception as e:
            print(f"Error saving login queue: {e}")
    

    def _load_login_queue(self):
        """Load login queue from file"""
        try:
            queue_file = os.path.join(tempfile.gettempdir(), "frt_login_queue.json")
            if not os.path.exists(queue_file):
                return
            
            with open(queue_file, 'r', encoding='utf-8') as f:
                queue_data = json.load(f)
            
            # Temporarily disable saving during bulk load
            self._loading_queue = True
            for account_data in queue_data:
                self.add_account_to_queue(account_data)
            self._loading_queue = False
            
            if hasattr(self, 'queue_count_label'):
                self.queue_count_label.setText(f"{len(queue_data)} accounts in queue")
        except Exception as e:
            self._loading_queue = False
            print(f"Error loading login queue: {e}")


    def queue_all_accounts(self):
        """Add all accounts from account_backup to the login queue — I/O in background."""
        backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")
        if not os.path.exists(backup_folder):
            QMessageBox.warning(self, "Error", "account_backup folder not found")
            return

        self.add_activity("Loading accounts...")

        def _load():
            accounts = []
            try:
                for entry in sorted(os.scandir(backup_folder), key=lambda e: e.name):
                    if not entry.is_dir(): continue
                    info_path = os.path.join(entry.path, "account_info.json")
                    if not os.path.exists(info_path): continue
                    try:
                        with open(info_path, 'r', encoding='utf-8-sig') as f:
                            accounts.append(json.load(f))
                    except Exception: continue
            except Exception as e:
                self.add_activity(f"Error scanning accounts: {e}")
            from PyQt6.QtCore import QMetaObject, Qt
            self._queue_all_pending = accounts
            QMetaObject.invokeMethod(self, "_apply_queue_all_accounts", Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=_load, daemon=True).start()

    @pyqtSlot()
    def _apply_queue_all_accounts(self):
        """Apply loaded accounts to login queue on main thread."""
        accounts = getattr(self, '_queue_all_pending', [])
        added = 0
        for data in accounts:
            uid = data.get('account_uid') or data.get('uid', '')
            name = data.get('full_name') or data.get('name') or uid
            # Skip duplicates
            already = any(
                self.login_queue_table.item(r, 1) and self.login_queue_table.item(r, 1).text() == uid
                for r in range(self.login_queue_table.rowCount())
            )
            if already: continue
            row = self.login_queue_table.rowCount()
            self.login_queue_table.insertRow(row)
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, data)
            self.login_queue_table.setItem(row, 0, name_item)
            self.login_queue_table.setItem(row, 1, QTableWidgetItem(uid))
            status_item = QTableWidgetItem("Queued")
            status_item.setForeground(QColor("#888888"))
            self.login_queue_table.setItem(row, 2, status_item)
            added += 1
        count = self.login_queue_table.rowCount()
        if hasattr(self, 'queue_count_label'):
            self.queue_count_label.setText(f"{count} accounts in queue")
        self.add_activity(f"Added {added} accounts to queue ({count} total)")


    def refresh_batch_devices(self):
        """Refresh device cards in the middle panel"""
        adb_path = os.path.join(_PROJECT_ROOT, "platform-tools", "adb.exe")
        if not os.path.exists(adb_path):
            adb_path = "adb"
        try:
            result = safe_subprocess_run([adb_path, "devices"], capture_output=True, text=True, timeout=10)
            lines = result.stdout.strip().split('\n')
            devices = []
            for line in lines[1:]:
                if '\t' in line:
                    did, status = line.split('\t', 1)
                    if status.strip() == 'device':
                        devices.append(did.strip())
        except Exception as e:
            self.add_activity(f"Device scan error: {e}")
            return

        # Rebuild device cards
        layout = self.device_cards_layout
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.batch_device_cards.clear()

        self.login_device_select.setRowCount(0)

        import tempfile
        proxy_cache = {}
        try:
            cf = os.path.join(tempfile.gettempdir(), "frt_device_proxy_cache.json")
            if os.path.exists(cf):
                with open(cf, 'r', encoding='utf-8') as f: proxy_cache = json.load(f)
        except: pass
        spoof_cache = {}
        try:
            sf = os.path.join(tempfile.gettempdir(), "frt_device_spoof_cache.json")
            if os.path.exists(sf):
                with open(sf, 'r', encoding='utf-8') as f: spoof_cache = json.load(f)
        except: pass

        for idx, did in enumerate(devices):
            proxy = proxy_cache.get(did, '—')
            spoof = spoof_cache.get(did, '—')
            row = self.login_device_select.rowCount()
            self.login_device_select.insertRow(row)
            self.login_device_select.setRowHeight(row, 32)
            d_item = QTableWidgetItem(f"{idx+1}. {did}"); d_item.setForeground(QColor("#4CAF50"))
            p_item = QTableWidgetItem(proxy); p_item.setForeground(QColor("#FF9800") if proxy != '—' else QColor("#888888"))
            s_item = QTableWidgetItem(spoof); s_item.setForeground(QColor("#FF9800") if spoof != '—' else QColor("#888888"))
            for col, item in enumerate([d_item, p_item, s_item]):
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.login_device_select.setItem(row, col, item)
            # Batch device card (for progress display)
            card = QFrame()
            card.setStyleSheet("QFrame { background-color: #1e1e1e; border: 1px solid #3e3e42; border-radius: 2px; }")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 6, 8, 6)
            card_layout.setSpacing(2)
            id_lbl = QLabel(did)
            id_lbl.setStyleSheet("color: #cccccc; font-size: 11px; font-weight: 600; background: transparent;")
            status_lbl = QLabel("Idle")
            status_lbl.setStyleSheet("color: #888; font-size: 10px; background: transparent;")
            progress_lbl = QLabel("")
            progress_lbl.setStyleSheet("color: #0e639c; font-size: 10px; background: transparent;")
            card_layout.addWidget(id_lbl)
            card_layout.addWidget(status_lbl)
            card_layout.addWidget(progress_lbl)
            layout.insertWidget(layout.count() - 1, card)
            self.batch_device_cards[did] = {
                'card': card, 'status_lbl': status_lbl, 'progress_lbl': progress_lbl
            }

        if devices:
            self.add_activity(f"Found {len(devices)} device(s)")
        else:
            no_dev = QLabel("No devices connected")
            no_dev.setStyleSheet("color: #555; font-size: 11px; background: transparent; padding: 10px;")
            layout.insertWidget(0, no_dev)
            self.add_activity("No devices found")


    def _set_device_card_status(self, device_id, status_text, color="#888888", progress=""):
        """Update a device card status label (thread-safe)"""
        from PyQt6.QtCore import QTimer as _QT
        def _update():
            if hasattr(self, 'batch_device_cards') and device_id in self.batch_device_cards:
                info = self.batch_device_cards[device_id]
                info['status_lbl'].setText(status_text)
                info['status_lbl'].setStyleSheet(f"color: {color}; font-size: 10px; background: transparent;")
                if progress:
                    info['progress_lbl'].setText(progress)
        _QT.singleShot(0, _update)


    def start_batch_restore(self):
        """Distribute queued accounts across all connected devices in parallel threads"""
        total_accounts = self.login_queue_table.rowCount()
        if total_accounts == 0:
            QMessageBox.warning(self, "No Accounts", "Add accounts to the queue first.")
            return
        if not self.batch_device_cards:
            QMessageBox.warning(self, "No Devices", "No devices found. Click Refresh first.")
            return

        devices = list(self.batch_device_cards.keys())
        cooldown = self.batch_cooldown_spin.value()

        accounts = []
        for row in range(total_accounts):
            name_item = self.login_queue_table.item(row, 0)
            if name_item:
                data = name_item.data(Qt.ItemDataRole.UserRole)
                if data:
                    accounts.append((row, data))

        if not accounts:
            QMessageBox.warning(self, "No Data", "Queue has rows but no account data. Re-add accounts.")
            return

        # Round-robin distribution
        device_queues = {d: [] for d in devices}
        for i, (row, data) in enumerate(accounts):
            device_queues[devices[i % len(devices)]].append((row, data))

        self.start_batch_btn.setEnabled(False)
        self.stop_login_btn.setEnabled(True)
        self._stop_login_requested = False
        self.login_status_label.setText(f"Batch: {len(accounts)} accounts on {len(devices)} device(s)")
        self.login_status_label.setStyleSheet("color: #FF9800; font-size: 10px; background: transparent;")

        import threading, time as _time

        def worker(device_id, queue):
            done = 0
            total = len(queue)
            self._set_device_card_status(device_id, "Running", "#FF9800", f"0/{total}")
            for row, account_data in queue:
                if self._stop_login_requested:
                    break
                name = account_data.get('full_name') or account_data.get('account_uid', f'row{row}')
                self._set_device_card_status(device_id, f"{name[:16]}", "#FF9800", f"{done}/{total}")
                from PyQt6.QtCore import QTimer as _QT2
                def _set_restoring(r=row):
                    it = self.login_queue_table.item(r, 2)
                    if it:
                        it.setText("Restoring...")
                        it.setForeground(QColor("#FF9800"))
                _QT2.singleShot(0, _set_restoring)

                success, msg = self.restore_account_session(account_data, device_id)
                done += 1
                result_txt = "Done" if success else "Failed"
                result_col = "#4CAF50" if success else "#f44336"

                from PyQt6.QtCore import QTimer as _QT3
                def _set_done(r=row, t=result_txt, c=result_col):
                    it = self.login_queue_table.item(r, 2)
                    if it:
                        it.setText(t)
                        it.setForeground(QColor(c))
                _QT3.singleShot(0, _set_done)

                self.add_activity(f"[{device_id}] {'OK' if success else 'FAIL'} {name}: {msg}")
                self._set_device_card_status(device_id, result_txt, result_col, f"{done}/{total}")

                if done < total and cooldown > 0 and not self._stop_login_requested:
                    _time.sleep(cooldown)

            final = "Stopped" if self._stop_login_requested else f"Done {done}/{total}"
            self._set_device_card_status(device_id, final, "#888" if self._stop_login_requested else "#4CAF50", f"{done}/{total}")

        threads = []
        for device_id, queue in device_queues.items():
            if queue:
                t = threading.Thread(target=worker, args=(device_id, queue), daemon=True)
                t.start()
                threads.append(t)

        def wait_all():
            for t in threads:
                t.join()
            from PyQt6.QtCore import QTimer as _QT4
            def _finish():
                self.start_batch_btn.setEnabled(True)
                self.stop_login_btn.setEnabled(False)
                self.login_status_label.setText("Batch complete.")
                self.login_status_label.setStyleSheet("color: #4CAF50; font-size: 10px; background: transparent;")
            _QT4.singleShot(0, _finish)

        threading.Thread(target=wait_all, daemon=True).start()


    def _refresh_all_devices(self):
        """Refresh devices in all locations (Login tab, Settings tab, Auto Reg tab, etc.)"""
        self.load_login_devices()
        self.refresh_devices()
        if hasattr(self, 'auto_reg_device_select'):
            self.load_auto_reg_devices()
        if hasattr(self, 'seed_device_table'):
            self._load_seeding_devices()
        self.add_activity("Refreshed device list in all tabs")


    def load_login_devices(self):
        """Load connected devices into the login device table with proxy and device changer info"""
        import threading, tempfile
        
        # Show loading message
        if hasattr(self, 'login_status_label'):
            self.login_status_label.setText("Scanning for devices...")
            self.login_status_label.setStyleSheet("QLabel { background: transparent; color: #FF9800; font-size: 11px; font-weight: 500; padding: 0; border: none; }")
        
        def _scan():
            """Background thread: scan devices and gather data"""
            try:
                adb_path = self.adb_path
                if not os.path.exists(adb_path) and adb_path != "adb":
                    self._login_devices_signal.emit([])  # Empty list = ADB not found
                    return

                # Load proxy and spoof caches
                proxy_cache = {}
                try:
                    cf = os.path.join(tempfile.gettempdir(), "frt_device_proxy_cache.json")
                    if os.path.exists(cf):
                        with open(cf, 'r', encoding='utf-8') as f: 
                            proxy_cache = json.load(f)
                except: 
                    pass

                spoof_cache = {}
                try:
                    sf = os.path.join(tempfile.gettempdir(), "frt_device_spoof_cache.json")
                    if os.path.exists(sf):
                        with open(sf, 'r', encoding='utf-8') as f: 
                            spoof_cache = json.load(f)
                except: 
                    pass

                # ADB scan (the slow part - runs in background)
                result = safe_subprocess_run([adb_path, "devices"], capture_output=True, text=True, timeout=10)
                lines = result.stdout.strip().split('\n')

                devices = []
                for line in lines[1:]:
                    if '\t' in line:
                        device_id, status = line.split('\t')
                        if status.strip() == 'device':
                            device_id = device_id.strip()
                            proxy = proxy_cache.get(device_id, '—')
                            spoof = spoof_cache.get(device_id, '—')
                            devices.append((device_id, proxy, spoof))

                # Emit signal with device data
                self._login_devices_signal.emit(devices)
                
            except Exception as e:
                print(f"Error scanning login devices: {e}")
                self._login_devices_signal.emit([])  # Empty list on error
        
        # Start background thread
        threading.Thread(target=_scan, daemon=True).start()
    
    
    def _apply_login_devices(self, devices):
        """Apply device list to login table (runs on main thread via signal)"""
        try:
            if not hasattr(self, 'login_device_select'):
                return
            
            # Handle error cases
            if devices is None or (isinstance(devices, list) and len(devices) == 0):
                # Check if it's ADB not found or just no devices
                adb_path = self.adb_path
                if not os.path.exists(adb_path) and adb_path != "adb":
                    self.login_status_label.setText("ADB not found")
                    self.login_status_label.setStyleSheet("QLabel { background: transparent; color: #f44336; font-size: 11px; font-weight: 500; padding: 0; border: none; }")
                else:
                    self.login_status_label.setText("No devices")
                    self.login_status_label.setStyleSheet("QLabel { background: transparent; color: #FF9800; font-size: 11px; font-weight: 500; padding: 0; border: none; }")
                self.login_device_select.setRowCount(0)
                return
            
            # Clear table
            self.login_device_select.setRowCount(0)
            
            # Populate table
            device_count = 0
            for device_id, proxy, spoof in devices:
                device_count += 1
                row = self.login_device_select.rowCount()
                self.login_device_select.insertRow(row)
                self.login_device_select.setRowHeight(row, 32)

                d_item = QTableWidgetItem(f"{device_count}. {device_id}")
                d_item.setForeground(QColor("#4CAF50"))
                p_item = QTableWidgetItem(proxy)
                p_item.setForeground(QColor("#FF9800") if proxy != '—' else QColor("#888888"))
                s_item = QTableWidgetItem(spoof)
                s_item.setForeground(QColor("#FF9800") if spoof != '—' else QColor("#888888"))

                for col, item in enumerate([d_item, p_item, s_item]):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self.login_device_select.setItem(row, col, item)

            # Update status label
            if device_count > 0:
                self.login_status_label.setText(f"{device_count} device(s)")
                self.login_status_label.setStyleSheet("QLabel { background: transparent; color: #4CAF50; font-size: 11px; font-weight: 500; padding: 0; border: none; }")
            else:
                self.login_status_label.setText("No devices")
                self.login_status_label.setStyleSheet("QLabel { background: transparent; color: #FF9800; font-size: 11px; font-weight: 500; padding: 0; border: none; }")
                
        except Exception as e:
            print(f"Error applying login devices: {e}")


    def _open_advanced_settings(self):
        """Open advanced settings dialog for batch rotation"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Advanced Settings - Batch Rotation")
        dialog.setMinimumWidth(650)
        dialog.setMinimumHeight(400)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("🔄 Batch Rotation Settings")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FF9800; padding-bottom: 8px;")
        layout.addWidget(title)
        
        desc = QLabel("Configure batch processing for managing 1000+ accounts across multiple devices.")
        desc.setStyleSheet("font-size: 11px; color: #888888; padding-bottom: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("background-color: #3d3d3d; border: none;")
        layout.addWidget(sep1)
        
        # Enable batch mode
        self.batch_mode_enabled = QCheckBox("Enable Batch Rotation Mode")
        self.batch_mode_enabled.setChecked(getattr(self, '_batch_mode_enabled', False))
        self.batch_mode_enabled.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0;
                font-size: 13px;
                font-weight: bold;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #555555;
                border-radius: 4px;
                background-color: transparent;
            }
            QCheckBox::indicator:checked {
                background-color: #FF9800;
                border-color: #FF9800;
            }
            QCheckBox::indicator:hover {
                border-color: #FF9800;
            }
        """)
        layout.addWidget(self.batch_mode_enabled)
        
        # Settings group with 2-column grid layout
        settings_group = QWidget()
        settings_layout = QGridLayout(settings_group)
        settings_layout.setSpacing(12)
        settings_layout.setContentsMargins(0, 8, 0, 0)
        settings_layout.setColumnStretch(0, 1)
        settings_layout.setColumnStretch(1, 1)
        
        # LEFT COLUMN
        
        # Accounts per batch
        batch_size_label = QLabel("Accounts per batch:")
        batch_size_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        settings_layout.addWidget(batch_size_label, 0, 0)
        
        batch_size_container = QWidget()
        batch_size_layout = QHBoxLayout(batch_size_container)
        batch_size_layout.setContentsMargins(0, 0, 0, 0)
        batch_size_layout.setSpacing(8)
        
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 100)
        self.batch_size_spin.setValue(getattr(self, '_batch_size', 20))
        self.batch_size_spin.setFixedWidth(80)
        self.batch_size_spin.setStyleSheet("""
            QSpinBox {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 12px;
            }
            QSpinBox:focus {
                border-color: #4CAF50;
            }
        """)
        batch_size_layout.addWidget(self.batch_size_spin)
        
        batch_size_help = QLabel("(Match device count)")
        batch_size_help.setStyleSheet("color: #666666; font-size: 10px;")
        batch_size_layout.addWidget(batch_size_help)
        batch_size_layout.addStretch()
        
        settings_layout.addWidget(batch_size_container, 1, 0)
        
        # Auto-clear Facebook data
        self.batch_auto_clear = QCheckBox("Auto-clear Facebook data")
        self.batch_auto_clear.setChecked(getattr(self, '_batch_auto_clear', True))
        self.batch_auto_clear.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #555555;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border-color: #4CAF50;
            }
        """)
        settings_layout.addWidget(self.batch_auto_clear, 2, 0)
        
        clear_help = QLabel("⚠️ CRITICAL: Prevents conflicts")
        clear_help.setStyleSheet("color: #FF9800; font-size: 10px; padding-left: 26px;")
        settings_layout.addWidget(clear_help, 3, 0)
        
        # RIGHT COLUMN
        
        # Cooldown between batches
        cooldown_label = QLabel("Cooldown between batches:")
        cooldown_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        settings_layout.addWidget(cooldown_label, 0, 1)
        
        cooldown_container = QWidget()
        cooldown_layout = QHBoxLayout(cooldown_container)
        cooldown_layout.setContentsMargins(0, 0, 0, 0)
        cooldown_layout.setSpacing(8)
        
        self.batch_cooldown_spin = QSpinBox()
        self.batch_cooldown_spin.setRange(0, 600)
        self.batch_cooldown_spin.setValue(getattr(self, '_batch_cooldown', 60))
        self.batch_cooldown_spin.setSuffix(" sec")
        self.batch_cooldown_spin.setFixedWidth(100)
        self.batch_cooldown_spin.setStyleSheet("""
            QSpinBox {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 12px;
            }
            QSpinBox:focus {
                border-color: #4CAF50;
            }
        """)
        cooldown_layout.addWidget(self.batch_cooldown_spin)
        
        cooldown_help = QLabel("(Min 60 sec)")
        cooldown_help.setStyleSheet("color: #666666; font-size: 10px;")
        cooldown_layout.addWidget(cooldown_help)
        cooldown_layout.addStretch()
        
        settings_layout.addWidget(cooldown_container, 1, 1)
        
        # Auto-backup sessions
        self.batch_auto_backup = QCheckBox("Auto-backup sessions")
        self.batch_auto_backup.setChecked(getattr(self, '_batch_auto_backup', False))
        self.batch_auto_backup.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #555555;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border-color: #4CAF50;
            }
        """)
        settings_layout.addWidget(self.batch_auto_backup, 2, 1)
        
        backup_help = QLabel("Saves updated tokens")
        backup_help.setStyleSheet("color: #666666; font-size: 10px; padding-left: 26px;")
        settings_layout.addWidget(backup_help, 3, 1)
        
        layout.addWidget(settings_group)
        
        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background-color: #3d3d3d; border: none;")
        layout.addWidget(sep2)
        
        # Info box
        info_box = QLabel(
            "💡 <b>How it works:</b><br>"
            "• Processes accounts in batches (e.g., 20 at a time)<br>"
            "• Waits cooldown period between batches<br>"
            "• Clears Facebook data to prevent conflicts<br>"
            "• Safe for managing 1000+ accounts on 20 devices"
        )
        info_box.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 12px;
                font-size: 11px;
            }
        """)
        info_box.setWordWrap(True)
        layout.addWidget(info_box)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setFixedWidth(100)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                border-color: #f44336;
                color: #f44336;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Settings")
        save_btn.setFixedHeight(36)
        save_btn.setFixedWidth(120)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        save_btn.clicked.connect(lambda: self._save_advanced_settings(dialog))
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    

    def _save_advanced_settings(self, dialog):
        """Save advanced settings and close dialog"""
        self._batch_mode_enabled = self.batch_mode_enabled.isChecked()
        self._batch_size = self.batch_size_spin.value()
        self._batch_cooldown = self.batch_cooldown_spin.value()
        self._batch_auto_clear = self.batch_auto_clear.isChecked()
        self._batch_auto_backup = self.batch_auto_backup.isChecked()
        
        # Update button text to show batch mode status
        if self._batch_mode_enabled:
            self.advanced_settings_btn.setText(f"  Advanced Settings (Batch: {self._batch_size} accounts)")
            self.advanced_settings_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #FF9800;
                    font-size: 12px;
                    border: 1px solid #FF9800;
                    border-radius: 6px;
                    text-align: left;
                    padding-left: 8px;
                }
                QPushButton:hover { 
                    background-color: rgba(255, 152, 0, 0.1);
                }
            """)
        else:
            self.advanced_settings_btn.setText("  Advanced Settings")
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
        
        self.add_activity(f"Batch settings saved: Mode={'ON' if self._batch_mode_enabled else 'OFF'}, Size={self._batch_size}, Cooldown={self._batch_cooldown}s")
        dialog.accept()
    

    def start_login_process(self):
        """Start the login process - restores session for each queued account"""
        if self.login_queue_table.rowCount() == 0:
            QMessageBox.warning(self, "No Accounts", "Please add accounts to the login queue first!")
            return

        # Get selected devices (use Ctrl+Click or Shift+Click or drag to select multiple)
        selected_items = self.login_device_select.selectedItems()
        # Get selected devices from table
        selected_rows = self.login_device_select.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Device", "Please select at least one device!")
            return

        devices = []
        for idx in selected_rows:
            item = self.login_device_select.item(idx.row(), 0)
            if item:
                text = item.text()
                device_id = text.split('. ', 1)[-1].strip()
                devices.append(device_id)

        self.login_btn.setEnabled(False)
        self.restore_session_btn.setEnabled(False)
        self.stop_login_btn.setEnabled(True)
        self._stop_login_requested = False

        def run_restore():
            total = self.login_queue_table.rowCount()
            device_idx = 0  # Round-robin device assignment
            
            for row in range(total):
                if self._stop_login_requested:
                    break
                name_item = self.login_queue_table.item(row, 0)
                if not name_item:
                    continue
                account_data = name_item.data(Qt.ItemDataRole.UserRole)
                if not account_data:
                    continue

                # Assign device in round-robin fashion
                device = devices[device_idx % len(devices)]
                device_idx += 1

                display_name = account_data.get('full_name') or account_data.get('account_uid') or account_data.get('uid') or f'Row {row+1}'
                
                # Update "Assigned To" column (col 5)
                assigned_item = self.login_queue_table.item(row, 5)
                if assigned_item:
                    assigned_item.setText(device)  # Show full device ID
                    assigned_item.setForeground(QColor("#4CAF50"))
                
                # Update status cell (col 6)
                status_item = self.login_queue_table.item(row, 6)
                if status_item:
                    status_item.setText(f"Restoring...")
                    status_item.setForeground(QColor("#FF9800"))

                self.login_status_label.setText(f"Restoring: {display_name} → {device[:8]} ({row+1}/{total})")
                self.login_status_label.setStyleSheet("QLabel { background-color: transparent; color: #FF9800; font-size: 12px; }")

                success, msg = self.restore_account_session(account_data, device)

                if status_item:
                    if success:
                        status_item.setText("Done")
                        status_item.setForeground(QColor("#4CAF50"))
                    else:
                        status_item.setText("Failed")
                        status_item.setForeground(QColor("#f44336"))

                self.add_activity(f"[{device[:8]}] {'OK' if success else 'FAIL'} {display_name}: {msg}")

            self.login_btn.setEnabled(True)
            self.restore_session_btn.setEnabled(True)
            self.stop_login_btn.setEnabled(False)
            if self._stop_login_requested:
                self.login_status_label.setText("Stopped by user.")
            else:
                self.login_status_label.setText(f"Done. Processed {total} account(s) on {len(devices)} device(s).")
            self.login_status_label.setStyleSheet("QLabel { background-color: transparent; color: #4CAF50; font-size: 12px; }")

        import threading
        threading.Thread(target=run_restore, daemon=True).start()


    def restore_account_session(self, account_data, device_id):
        """
        Restore Facebook session + Device.xml to device.
        Uses legacy method for reliability (fast restore has session issues).
        Returns (success: bool, message: str)
        """
        # Use legacy method - it's slower but reliable
        # Fast restore has issues with session restoration
        return self._restore_account_session_legacy(account_data, device_id)
    
    def _restore_account_session_fast_DISABLED(self, account_data, device_id):
        """
        Fast restore - DISABLED due to session restoration issues.
        Kept for reference only.
        """
        # Use fast restore for 10x speed improvement
        try:
            from src.utils.fast_restore import FastRestore
            
            def log(msg):
                self.add_activity(f"  [FastRestore] {msg}")
            
            fast_restore = FastRestore(self.adb_path, log_fn=log)
            
            uid = account_data.get('account_uid', account_data.get('uid', ''))
            if not uid:
                return False, "No UID in account data"
            
            # Find backup folder
            backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")
            acc_folder = None
            for entry in os.scandir(backup_folder):
                if entry.is_dir() and entry.name.startswith(uid):
                    acc_folder = entry.path
                    break
            
            if not acc_folder:
                return False, f"Backup folder not found for UID {uid}"
            
            log(f"Starting fast restore for {uid} on {device_id[-8:]}")
            success, message, duration = fast_restore.restore_account_fast(account_data, device_id, acc_folder)
            
            if success:
                log(f"✓ Restore completed in {duration:.1f}s")
                return True, f"Session restored in {duration:.1f}s"
            else:
                log(f"✗ Restore failed: {message}")
                return False, message
                
        except Exception as e:
            self.add_activity(f"  [FastRestore] Error: {e}")
            # Fall back to old method if fast restore fails
            return self._restore_account_session_legacy(account_data, device_id)
    
    def _restore_account_session_legacy(self, account_data, device_id):
        """
        Legacy restore method - slower but reliable.
        Returns (success: bool, message: str)
        """
        import tarfile, tempfile, shutil

        def log(msg):
            self.add_activity(f"  [Restore] {msg}")

        uid = account_data.get('account_uid', account_data.get('uid', ''))
        if not uid:
            return False, "No UID in account data"

        log(f"UID: {uid} | Device: {device_id}")

        # Locate account backup folder
        backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")
        acc_folder = None
        for entry in os.scandir(backup_folder):
            if entry.is_dir() and entry.name.startswith(uid):
                acc_folder = entry.path
                break

        if not acc_folder:
            return False, f"Backup folder not found for UID {uid}"

        log(f"Backup folder: {os.path.basename(acc_folder)}")

        adb_path = self.adb_path

        log(f"ADB: {adb_path}")

        def adb(*args, timeout=30):
            return safe_subprocess_run(
                [adb_path, "-s", device_id] + list(args),
                capture_output=True, text=True, timeout=timeout
            )

        def adb_shell(cmd, timeout=30):
            r = adb("shell", cmd, timeout=timeout)
            out = (r.stdout + r.stderr).strip()
            return out

        # ── Step 1: Check ADB connection ─────────────────────────────────
        r = adb("get-state", timeout=5)
        state = (r.stdout + r.stderr).strip()
        log(f"Device state: {state}")
        if "device" not in state:
            return False, f"Device not connected or unauthorized (state: {state})"

        # ── Step 2: Check root ────────────────────────────────────────────
        out = adb_shell('su -c "id"', timeout=10)
        log(f"Root check: {out[:80]}")
        if "uid=0" not in out:
            return False, f"Device not rooted. su output: {out[:80]}"

        # ── Step 3: Force stop Facebook ───────────────────────────────────
        log("Force stopping Facebook...")
        r1 = adb_shell("am force-stop com.facebook.katana")
        r2 = adb_shell("am force-stop com.facebook.lite")
        log(f"  katana: {r1 or 'ok'} | lite: {r2 or 'ok'}")

        # ── Step 4: Restore Device.xml (MaxChanger) ───────────────────────
        device_subfolder = os.path.join(acc_folder, "Device info")
        log(f"Device info folder exists: {os.path.exists(device_subfolder)}")

        def find_device_xml(base):
            """Find Device.xml in extracted folder tree"""
            for root, dirs, files in os.walk(base):
                if 'Device.xml' in files:
                    return os.path.join(root, 'Device.xml')
            return None

        # Keep xml_local alive for Step 6 (resetprop) — don't clean up tmp_dev early
        xml_local_for_resetprop = None
        tmp_dev_for_resetprop = None  # cleaned up after Step 6

        if os.path.exists(device_subfolder):
            tar_files = [f for f in os.listdir(device_subfolder) if f.endswith(('.tar.gz', '.tgz', '.tar'))]
            log(f"Device tar files: {tar_files}")

            xml_local = None
            tmp_dev = None

            if tar_files:
                # Case A: tar.gz present - extract it
                tmp_dev = tempfile.mkdtemp()
                try:
                    with tarfile.open(os.path.join(device_subfolder, tar_files[0]), 'r:*') as tar:
                        tar.extractall(tmp_dev)
                    xml_local = find_device_xml(tmp_dev)
                    log(f"Device.xml from tar: {xml_local}")
                except Exception as e:
                    log(f"  Device tar extract error: {e}")
            else:
                # Case B: already extracted - find Device.xml directly
                xml_local = find_device_xml(device_subfolder)
                log(f"Device.xml from extracted folder: {xml_local}")

            # Save for Step 6 before tmp_dev is cleaned up
            if xml_local and os.path.exists(xml_local):
                xml_local_for_resetprop = xml_local
                tmp_dev_for_resetprop = tmp_dev  # don't clean yet

            if xml_local and os.path.exists(xml_local):
                tmp_remote = "/data/local/tmp/Device.xml"
                dest_dir = "/data/data/com.minsoftware.maxchanger/shared_prefs/"
                log(f"Pushing Device.xml...")

                import tempfile as _tf
                tmp_xml_dir = _tf.mkdtemp()
                tmp_xml_local = os.path.join(tmp_xml_dir, "Device.xml")
                try:
                    # ── Patch Device.xml before pushing ──────────────────────────
                    # MaxChanger's BuildHook reads via XSharedPreferences.
                    # It needs: buildtime (long), build_display, cpu_abi, cpu_abi2,
                    # radioVersion, gpuVersion — keys that may be missing from backup.
                    import xml.etree.ElementTree as _ET2
                    _tree2 = _ET2.parse(xml_local)
                    _root2 = _tree2.getroot()
                    _existing_keys = {e.get('name') for e in _root2}

                    def _add_xml_str(name, value):
                        if name not in _existing_keys and value:
                            e = _ET2.SubElement(_root2, 'string')
                            e.set('name', name)
                            e.text = str(value)
                            _existing_keys.add(name)

                    def _add_xml_long(name, value):
                        if name not in _existing_keys and value:
                            e = _ET2.SubElement(_root2, 'long')
                            e.set('name', name)
                            e.set('value', str(value))
                            _existing_keys.add(name)

                    # Get existing values for cross-mapping
                    _xprops = {e.get('name'): (e.get('value') or e.text or '') for e in _root2}

                    # buildtime as Long (hook does Long.parseLong on this key)
                    _bt = _xprops.get('build_time') or _xprops.get('buildtime', '')
                    if _bt and _bt.strip().lstrip('-').isdigit():
                        _add_xml_long('buildtime', _bt.strip())
                        _add_xml_str('buildtime', _bt.strip())
                    # build_display for Build.DISPLAY
                    _disp = _xprops.get('display') or _xprops.get('build_display', '')
                    _add_xml_str('build_display', _disp)
                    # radioVersion alias
                    _rv = _xprops.get('radio_version') or _xprops.get('radioVersion', '')
                    _add_xml_str('radioVersion', _rv)
                    # cpu_abi / cpu_abi2
                    _abilist = _xprops.get('cpu_abilist', '')
                    _abis = [a.strip() for a in _abilist.split(',') if a.strip()]
                    _add_xml_str('cpu_abi', _abis[0] if _abis else 'arm64-v8a')
                    _add_xml_str('cpu_abi2', _abis[1] if len(_abis) > 1 else 'armeabi-v7a')
                    _add_xml_str('gpuVersion', _xprops.get('gpuVersion', 'unknown'))
                    # androidId (camelCase) — MaxChanger hook reads this key, not 'android_id'
                    _aid = _xprops.get('android_id') or _xprops.get('androidId', '')
                    _add_xml_str('androidId', _aid)

                    _tree2.write(tmp_xml_local, encoding='utf-8', xml_declaration=True)
                    log(f"  Device.xml patched (buildtime={_bt[:20] if _bt else 'N/A'})")

                    pr = safe_subprocess_run(
                        [adb_path, "-s", device_id, "push", tmp_xml_local, tmp_remote],
                        capture_output=True, text=True, timeout=30
                    )
                    push_out = (pr.stdout + pr.stderr).strip()
                    log(f"  push: {push_out[:120]}")

                    check = adb_shell(f"ls {tmp_remote}")
                    log(f"  verify tmp: {check[:60]}")
                    if "No such file" in check or not check.strip():
                        log(f"  WARNING: Device.xml push failed, skipping mv")
                    else:
                        # Get MaxChanger UID for correct ownership
                        _mc_uid = adb_shell('su -c "stat -c %u /data/data/com.minsoftware.maxchanger"').strip()
                        _chown = f" && chown {_mc_uid}:{_mc_uid} {dest_dir}Device.xml" if _mc_uid.isdigit() else ""
                        adb_shell(f'su -c "mkdir -p {dest_dir}"')
                        result = adb_shell(
                            f'su -c "mv {tmp_remote} {dest_dir}Device.xml && chmod 664 {dest_dir}Device.xml{_chown}"'
                        )
                        log(f"  mv: {result[:100] or 'ok'}")
                        if "Permission denied" in result or "No such file" in result:
                            log(f"  WARNING: Device.xml mv failed: {result[:100]}")
                        else:
                            log("  Device.xml restored + patched OK")
                except Exception as _xe:
                    log(f"  Device.xml patch error: {_xe} — pushing original")
                    shutil.copy2(xml_local, tmp_xml_local)
                    safe_subprocess_run(
                        [adb_path, "-s", device_id, "push", tmp_xml_local, tmp_remote],
                        capture_output=True, text=True, timeout=30
                    )
                    adb_shell(f'su -c "mv {tmp_remote} {dest_dir}Device.xml && chmod 664 {dest_dir}Device.xml"')
                finally:
                    shutil.rmtree(tmp_xml_dir, ignore_errors=True)
            else:
                log("  Device.xml not found - skipping")

            # Don't clean tmp_dev here — keep it alive for Step 6 (resetprop)
            # It will be cleaned after Step 6 completes

        # ── Step 5: Restore Profile info (Facebook session) ───────────────
        profile_subfolder = os.path.join(acc_folder, "Profile info")
        log(f"Profile info folder exists: {os.path.exists(profile_subfolder)}")

        fb_data_local = None
        tmp_prof = None

        if os.path.exists(profile_subfolder):
            tar_files = [f for f in os.listdir(profile_subfolder) if f.endswith(('.tar.gz', '.tgz', '.tar'))]
            log(f"Profile tar files: {tar_files}")

            if tar_files:
                # Case A: tar.gz present - extract it
                tmp_prof = tempfile.mkdtemp()
                try:
                    with tarfile.open(os.path.join(profile_subfolder, tar_files[0]), 'r:*') as tar:
                        tar.extractall(tmp_prof)
                    for root, dirs, files in os.walk(tmp_prof):
                        if os.path.basename(root) == "com.facebook.katana":
                            fb_data_local = root
                            break
                    log(f"FB data from tar: {fb_data_local}")
                except Exception as e:
                    return False, f"Profile tar extract error: {e}"
            else:
                # Case B: already extracted - find com.facebook.katana directly
                for root, dirs, files in os.walk(profile_subfolder):
                    if os.path.basename(root) == "com.facebook.katana":
                        fb_data_local = root
                        break
                log(f"FB data from extracted folder: {fb_data_local}")

        if not fb_data_local or not os.path.exists(fb_data_local):
            return False, "Could not find com.facebook.katana data in backup"

        contents = os.listdir(fb_data_local)
        log(f"FB data contents ({len(contents)} items): {contents[:8]}")

        # ── Step 5.1: Remove prefs_db entirely for fresh device_id generation ──
        # CRITICAL FIX: prefs_db contains old device_id mapped to wrong device on server.
        # By removing it entirely, Facebook generates a FRESH device_id with the spoofed
        # identity, and the device name shows correctly IMMEDIATELY (no sync wait needed).
        # This matches the behavior of backups that work instantly (like Anita Debra backup).
        try:
            _prefs_db_local = os.path.join(fb_data_local, "databases", "prefs_db")
            _prefs_db_journal = os.path.join(fb_data_local, "databases", "prefs_db-journal")
            _prefs_db_shm = os.path.join(fb_data_local, "databases", "prefs_db-shm")
            _prefs_db_wal = os.path.join(fb_data_local, "databases", "prefs_db-wal")
            
            removed_count = 0
            for _db_file in [_prefs_db_local, _prefs_db_journal, _prefs_db_shm, _prefs_db_wal]:
                if os.path.exists(_db_file):
                    os.remove(_db_file)
                    removed_count += 1
            
            if removed_count > 0:
                log(f"  prefs_db removed ({removed_count} files) - Facebook will generate fresh device_id")
            else:
                log(f"  prefs_db not found in backup - Facebook will generate fresh device_id")
            
            # CRITICAL: Also remove default_phone_id which stores the device_id
            # This file is in app_light_prefs and contains the same device_id as prefs_db
            _phone_id_local = os.path.join(fb_data_local, "app_light_prefs", "com.facebook.katana", "default_phone_id")
            if os.path.exists(_phone_id_local):
                os.remove(_phone_id_local)
                log(f"  default_phone_id removed - ensures fresh device_id generation")
            
            # Also remove com.google.android.gms.appid.xml from local copy
            _gms_local = os.path.join(fb_data_local, "shared_prefs", "com.google.android.gms.appid.xml")
            if os.path.exists(_gms_local):
                os.remove(_gms_local)
                log(f"  removed com.google.android.gms.appid.xml from local backup copy")
        except Exception as _pe:
            log(f"  Warning: prefs_db removal error: {_pe}")

        # ── Step 5.2: Re-login via Facebook mobile API to get fresh session ──
        # This generates a new datr cookie tied to the spoofed device identity,
        # so "Where you're logged in" shows the correct device name.
        try:
            from src.utils.fb_relogin import relogin_and_get_fresh_session, update_auth_files_with_new_session
            _acc_json_path = os.path.join(acc_folder, "account_info.json")
            if os.path.exists(_acc_json_path):
                with open(_acc_json_path, 'r', encoding='utf-8') as _f:
                    _acc_json = json.load(_f)
                _phone    = _acc_json.get('phone', '')
                _email    = _acc_json.get('email', '')
                _password = _acc_json.get('password', '')
                _login_id = _phone or _email
                if _login_id and _password and xml_local_for_resetprop and os.path.exists(xml_local_for_resetprop):
                    log(f"Re-logging in as {_login_id[:6]}*** to get fresh session...")
                    _sess_ok, _sess = relogin_and_get_fresh_session(
                        phone_or_email=_login_id,
                        password=_password,
                        device_xml_path=xml_local_for_resetprop,
                        log_fn=lambda m: log(f"  {m}"),
                    )
                    if _sess_ok:
                        log(f"  Re-login OK — updating auth files with fresh session")
                        update_auth_files_with_new_session(
                            fb_data_local=fb_data_local,
                            uid=uid,
                            session=_sess,
                            log_fn=lambda m: log(f"  {m}"),
                        )
                    else:
                        log(f"  Re-login failed: {_sess.get('error','?')[:80]} — using backup session")
                else:
                    log("  No credentials for re-login — using backup session")
        except Exception as _rle:
            log(f"  Warning: re-login error: {_rle}")

        try:
            fb_dest = "/data/data/com.facebook.katana"
            tmp_remote_fb = "/data/local/tmp/fb_restore"

            log("Cleaning up old tmp on device...")
            adb_shell(f"rm -rf {tmp_remote_fb}")

            log(f"Pushing FB data to {tmp_remote_fb}...")
            r = safe_subprocess_run(
                [adb_path, "-s", device_id, "push", fb_data_local, tmp_remote_fb],
                capture_output=True, text=True, timeout=180
            )
            push_out = (r.stdout + r.stderr).strip()
            log(f"  push: {push_out[-150:] if len(push_out) > 150 else push_out}")
            if r.returncode != 0 and "error" in push_out.lower():
                return False, f"adb push failed: {push_out[:200]}"

            ls_out = adb_shell(f"ls {tmp_remote_fb}")
            log(f"  tmp contents: {ls_out[:100]}")

            fb_uid = adb_shell(f'su -c "stat -c %u {fb_dest}"', timeout=10)
            log(f"  FB app UID: {fb_uid}")
            if not fb_uid.isdigit():
                fb_uid = ""

            # Wipe existing Facebook data directories before restoring.
            # This prevents stale data from previous accounts mixing with new data.
            # We wipe only the data subdirs (not the app install itself).
            log("  Wiping old Facebook data dirs...")
            adb_shell(
                f'su -c "rm -rf {fb_dest}/app_light_prefs '
                f'{fb_dest}/databases '
                f'{fb_dest}/files '
                f'{fb_dest}/shared_prefs '
                f'{fb_dest}/cache '
                f'{fb_dest}/app_cache '
                f'{fb_dest}/app_textures '
                f'{fb_dest}/app_ras_blobs 2>/dev/null; '
                f'mkdir -p {fb_dest}/app_light_prefs {fb_dest}/databases {fb_dest}/files {fb_dest}/shared_prefs"',
                timeout=15
            )

            chown_part = f" && chown -R {fb_uid}:{fb_uid} {fb_dest}" if fb_uid else ""
            restore_cmd = f'su -c "cp -rp {tmp_remote_fb}/. {fb_dest}/ && chmod -R 771 {fb_dest}{chown_part}"'
            log("Running root copy...")
            result = adb_shell(restore_cmd, timeout=60)
            log(f"  copy: {result[:120] or 'ok'}")
            if "Permission denied" in result:
                return False, f"Root copy failed: {result[:120]}"

            adb_shell(f"rm -rf {tmp_remote_fb}")

            # ── Fix: ensure correct 'authentication' file is in place ────
            # The backup may contain multiple accounts' data. The 'authentication'
            # file must belong to OUR uid. Find it in app_light_prefs and push it
            # explicitly so it's never overwritten by a wrong-account copy.
            _alp_local = os.path.join(fb_data_local, "app_light_prefs", "com.facebook.katana")
            _auth_src = os.path.join(_alp_local, "authentication")
            _underlying_src = os.path.join(_alp_local, "underlying_account")
            _alp_dest = f"{fb_dest}/app_light_prefs/com.facebook.katana"

            for _src_file, _dest_name in [(_auth_src, "authentication"), (_underlying_src, "underlying_account")]:
                if os.path.exists(_src_file):
                    _tmp_push_path = f"/data/local/tmp/_fb_{_dest_name}"
                    safe_subprocess_run(
                        [adb_path, "-s", device_id, "push", _src_file, _tmp_push_path],
                        capture_output=True, text=True, timeout=30
                    )
                    _mv_r = adb_shell(
                        f'su -c "cp {_tmp_push_path} {_alp_dest}/{_dest_name} && '
                        f'chown {fb_uid or "u0_a133"}:{fb_uid or "u0_a133"} {_alp_dest}/{_dest_name} && '
                        f'chmod 771 {_alp_dest}/{_dest_name} && rm -f {_tmp_push_path}"'
                    )
                    log(f"  {_dest_name} pushed: {_mv_r[:60] or 'ok'}")

        except Exception as e:
            return False, f"Profile restore error: {e}"
        finally:
            if tmp_prof:
                shutil.rmtree(tmp_prof, ignore_errors=True)

        # ── Step 5.5: Write deviceJson.txt for MaxChanger hook ───────────────
        # MaxChanger's BuildHook reads from /data/local/tmp/nk/deviceJson.txt
        # (NOT from Device.xml). Field names confirmed from DEX analysis.
        log("Writing deviceJson.txt for MaxChanger hook...")
        try:
            # Reuse the already-extracted Device.xml from Step 4
            dev_xml_path = xml_local_for_resetprop

            dprops = {}
            if dev_xml_path and os.path.exists(dev_xml_path):
                import xml.etree.ElementTree as ET
                _tree = ET.parse(dev_xml_path)
                for elem in _tree.getroot():
                    dprops[elem.get('name', '')] = (elem.get('value') or elem.text or '').strip()

            # Fallback: fill missing keys from account_info.json device_info
            try:
                import json as _json_fb
                _jp = os.path.join(acc_folder, "account_info.json")
                if os.path.exists(_jp):
                    _ai = _json_fb.load(open(_jp, 'r', encoding='utf-8'))
                    _di = _ai.get('device_info', {})
                    # Only fill if Device.xml key is missing or empty
                    _fallbacks = {
                        'brand':        _di.get('manufacturer', ''),
                        'model':        _di.get('model', ''),
                        'manufacturer': _di.get('manufacturer', ''),
                        'android_id':   _di.get('android_id', ''),
                        'serial':       _di.get('serial', ''),
                        'fingerprint':  _di.get('fingerprint', ''),
                        'imei':         _di.get('imei', ''),
                        'wifi_mac':     _di.get('wifi_mac', ''),
                        'wifimac':      _di.get('wifi_mac', ''),
                        'release':      _di.get('android_version', ''),
                    }
                    for k, v in _fallbacks.items():
                        if not dprops.get(k) and v:
                            dprops[k] = v
            except Exception:
                pass

            # Build deviceJson using exact field names MaxChanger expects
            import json as _json, time as _time
            device_json = {
                "imei":         dprops.get('imei', ''),
                "board":        dprops.get('board', 'unknown'),
                "bootloader":   dprops.get('bootloader', 'unknown'),
                "brand":        dprops.get('brand', ''),
                "buildtime":    int(dprops['buildtime']) if dprops.get('buildtime', '').lstrip('-').isdigit() else (int(dprops['build_time']) if dprops.get('build_time', '').lstrip('-').isdigit() else int(_time.time() * 1000)),
                "cpu_abi":      dprops.get('cpu_abi', 'arm64-v8a'),
                "cpu_abi2":     dprops.get('cpu_abi2', 'armeabi-v7a'),
                "device":       dprops.get('device', ''),
                "display":      dprops.get('build_display', dprops.get('display', '')),
                "fingerprint":  dprops.get('fingerprint', ''),
                "gpuVersion":   dprops.get('gpuVersion', 'unknown'),
                "hardware":     dprops.get('hardware', 'unknown'),
                "host":         dprops.get('host', 'unknown'),
                "imsi":         dprops.get('imsi', ''),
                "incremental":  dprops.get('incremental', ''),
                "manufacturer": dprops.get('manufacturer', ''),
                "model":        dprops.get('model', ''),
                "product":      dprops.get('product', ''),
                "radioVersion": dprops.get('radioVersion', dprops.get('radio_version', '')),
                "release":      dprops.get('release', ''),
                "serial":       dprops.get('serial', ''),
                "simserial":    dprops.get('simserial', ''),
                "wifimac":      dprops.get('wifimac', dprops.get('wifi_mac', '')),
                "android_id":   dprops.get('android_id', ''),
                "androidId":    dprops.get('android_id', dprops.get('androidId', '')),
            }

            # Ensure buildtime is a valid Long (never empty string)
            if not isinstance(device_json["buildtime"], int) or device_json["buildtime"] == 0:
                device_json["buildtime"] = int(_time.time() * 1000)

            device_json_str = _json.dumps(device_json, separators=(',', ':'))
            log(f"  deviceJson brand={device_json.get('brand')} model={device_json.get('model')} buildtime={device_json.get('buildtime')}")

            # Write to a local temp file
            import tempfile as _tf2
            _tmp_nk_dir = _tf2.mkdtemp()
            _dj_local = os.path.join(_tmp_nk_dir, "deviceJson.txt")
            _path_local = os.path.join(_tmp_nk_dir, "PATH_DATABACK_JSON.txt")
            _pathback_local = os.path.join(_tmp_nk_dir, "PATH_BACK_PATH.txt")

            _run_local = os.path.join(_tmp_nk_dir, "run.txt")
            _sel_local = os.path.join(_tmp_nk_dir, "PATH_DATABACK_SELECTED_PATH.txt")

            with open(_dj_local, 'w', encoding='utf-8') as f:
                f.write(device_json_str)
            with open(_path_local, 'w', encoding='utf-8') as f:
                f.write("/data/local/tmp/nk/deviceJson.txt")
            with open(_pathback_local, 'w', encoding='utf-8') as f:
                f.write("/data/local/tmp/nk/")
            with open(_run_local, 'w', encoding='utf-8') as f:
                f.write("1")
            with open(_sel_local, 'w', encoding='utf-8') as f:
                f.write("/data/local/tmp/nk/deviceJson.txt")

            # Ensure /data/local/tmp is world-traversable so hook process can read nk/
            adb_shell('su -c "chmod 777 /data/local/tmp"')

            _nk_files = [
                (_dj_local,       "deviceJson.txt"),
                (_path_local,     "PATH_DATABACK_JSON.txt"),
                (_pathback_local, "PATH_BACK_PATH.txt"),
                (_run_local,      "run.txt"),
                (_sel_local,      "PATH_DATABACK_SELECTED_PATH.txt"),
            ]

            adb_shell('su -c "mkdir -p /data/local/tmp/nk && chmod 777 /data/local/tmp/nk"')
            adb_shell("mkdir -p /sdcard/nk")
            for _local_f, _fname in _nk_files:
                _tmp_push = f"/data/local/tmp/_nk_{_fname}"
                safe_subprocess_run(
                    [adb_path, "-s", device_id, "push", _local_f, _tmp_push],
                    capture_output=True, text=True, timeout=15
                )
                adb_shell(f'su -c "cp {_tmp_push} /data/local/tmp/nk/{_fname} && chmod 777 /data/local/tmp/nk/{_fname} && rm -f {_tmp_push}"')
                safe_subprocess_run(
                    [adb_path, "-s", device_id, "push", _local_f, f"/sdcard/nk/{_fname}"],
                    capture_output=True, text=True, timeout=15
                )

            log("  deviceJson.txt pushed to /data/local/tmp/nk/ and /sdcard/nk/")

            # Verify
            _verify = adb_shell('su -c "cat /data/local/tmp/nk/deviceJson.txt"')
            log(f"  verify deviceJson: {_verify[:80]}")

            import shutil as _sh2
            _sh2.rmtree(_tmp_nk_dir, ignore_errors=True)

        except Exception as e:
            log(f"  deviceJson write error: {e}")

        # ── Step 6: Apply device props via resetprop + launch ────────────────
        log("Applying device props via resetprop...")

        # Use the Device.xml we already extracted in Step 4 — don't re-walk
        xml_path = xml_local_for_resetprop

        if xml_path and os.path.exists(xml_path):
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(xml_path)
                props = {}
                for elem in tree.getroot():
                    props[elem.get('name', '')] = (elem.get('value') or elem.text or '').strip()

                # Map Device.xml keys to Android build props
                prop_map = {
                    'brand':        'ro.product.brand',
                    'manufacturer': 'ro.product.manufacturer',
                    'model':        'ro.product.model',
                    'device':       'ro.product.device',
                    'product':      'ro.product.name',
                    'fingerprint':  'ro.build.fingerprint',
                    'build_id':     'ro.build.id',
                    'release':      'ro.build.version.release',
                    'incremental':  'ro.build.version.incremental',
                    'bootloader':   'ro.bootloader',
                    'hardware':     'ro.hardware',
                    'serial':       'ro.serialno',
                    'android_id':   'ro.boot.android_id',
                }

                # display field: Device.xml may use 'display' or 'build_display'
                display_val = props.get('display') or props.get('build_display', '')
                if display_val:
                    props['_display_resolved'] = display_val
                    prop_map['_display_resolved'] = 'ro.build.display.id'

                reset_cmds = []
                for xml_key, prop_key in prop_map.items():
                    val = props.get(xml_key, '')
                    if val:
                        # Escape single quotes
                        val_esc = val.replace("'", "\\'")
                        reset_cmds.append(f"resetprop {prop_key} '{val_esc}'")

                if reset_cmds:
                    full_cmd = ' && '.join(reset_cmds)
                    result = adb_shell(f'su -c "{full_cmd}"', timeout=15)
                    log(f"  resetprop: {result[:80] or 'ok'}")
                else:
                    log("  No props to set")
            except Exception as e:
                log(f"  resetprop error: {e}")
        else:
            log("  Device.xml not found for resetprop")

        # ── Step 6.5: Fix android_id via Settings.Secure ─────────────────
        # resetprop ro.boot.android_id only sets a boot prop — Facebook reads
        # Settings.Secure.ANDROID_ID which comes from the settings provider DB.
        # We must write it directly via 'content' command as root.
        _android_id_val = ''
        try:
            import xml.etree.ElementTree as _ET3
            # Reuse the already-extracted Device.xml from Step 4
            _dev_xml3 = xml_local_for_resetprop
            if _dev_xml3 and os.path.exists(_dev_xml3):
                for _e3 in _ET3.parse(_dev_xml3).getroot():
                    if _e3.get('name') == 'android_id':
                        _android_id_val = (_e3.get('value') or _e3.text or '').strip()
                        break
        except Exception:
            pass

        if _android_id_val:
            log(f"Setting android_id via Settings.Secure: {_android_id_val}")
            # Write to settings provider (requires root)
            _aid_result = adb_shell(
                f'su -c "content insert --uri content://settings/secure '
                f'--bind name:s:android_id --bind value:s:{_android_id_val} 2>/dev/null; '
                f'content update --uri content://settings/secure '
                f'--bind value:s:{_android_id_val} --where \\"name=\'android_id\'\\" 2>/dev/null; '
                f'settings put secure android_id {_android_id_val}"',
                timeout=15
            )
            log(f"  android_id set: {_aid_result[:80] or 'ok'}")
            # Verify
            _aid_check = adb_shell("settings get secure android_id")
            log(f"  android_id verify: {_aid_check.strip()}")
        else:
            log("  android_id not found in Device.xml — skipping")

        # ── Step 6.6: Remove conflicting auth files ──────────────────────
        # msys-auth-data.xml stores the rt_client_id used for device recognition.
        # If the backup HAS its own msys-auth-data.xml (already restored via cp),
        # we must NOT delete it — it's what makes Facebook recognize the device.
        # Only delete it if the backup didn't include one (meaning it belongs to
        # a different account that was previously on this device).
        log("Removing conflicting auth files...")
        # Save Device.xml to a persistent copy for Step 6.9 API registration
        # BEFORE cleaning up the temp folder
        _device_xml_for_api_reg = None
        if xml_local_for_resetprop and os.path.exists(xml_local_for_resetprop):
            try:
                import tempfile as _tf_reg
                _reg_tmp = _tf_reg.mkdtemp()
                _device_xml_for_api_reg = os.path.join(_reg_tmp, "Device_reg.xml")
                shutil.copy2(xml_local_for_resetprop, _device_xml_for_api_reg)
            except Exception:
                _device_xml_for_api_reg = None
        # Now safe to clean up the Device.xml temp folder
        if tmp_dev_for_resetprop:
            shutil.rmtree(tmp_dev_for_resetprop, ignore_errors=True)
            tmp_dev_for_resetprop = None

        # Check if backup included its own msys-auth-data.xml
        _backup_has_msys = False
        try:
            import tarfile as _tf_msys
            _prof_dir = os.path.join(acc_folder, "Profile info")
            _tar_files_msys = [f for f in os.listdir(_prof_dir) if f.endswith(('.tar.gz', '.tgz', '.tar'))]
            if _tar_files_msys:
                with _tf_msys.open(os.path.join(_prof_dir, _tar_files_msys[0]), 'r:*') as _t_msys:
                    _backup_has_msys = any('msys-auth-data' in m.name for m in _t_msys.getmembers())
        except Exception:
            pass

        _conflict_files = [
            "/data/data/com.facebook.katana/shared_prefs/com.facebook.katana_preferences.xml",
        ]
        if not _backup_has_msys:
            # No msys-auth-data in backup — remove any stale one from previous account
            _conflict_files.insert(0, "/data/data/com.facebook.katana/shared_prefs/msys-auth-data.xml")
            log(f"  backup has no msys-auth-data.xml — removing stale device copy")
        else:
            log(f"  backup has msys-auth-data.xml — will overwrite with current android_id")
        for _cf in _conflict_files:
            _cf_check = adb_shell(f'su -c "ls {_cf} 2>/dev/null"')
            if _cf_check and "No such file" not in _cf_check:
                _cf_del = adb_shell(f'su -c "rm -f {_cf}"')
                log(f"  removed {os.path.basename(_cf)}: {_cf_del or 'ok'}")
            else:
                log(f"  {os.path.basename(_cf)}: not present")

        # ── Step 6.6b: Always inject msys-auth-data.xml with current android_id ──
        # The rt_client_id must match the current device's android_id for MQTT
        # to connect. Backup copies may have wrong/truncated values. Always
        # overwrite with the current spoofed android_id we set in Step 6.5.
        try:
            _current_aid = adb_shell("settings get secure android_id").strip()
            if _current_aid and len(_current_aid) >= 8 and 'null' not in _current_aid:
                _msys_content = (
                    "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n"
                    "<map>\n"
                    f'    <string name="{uid}-_rt_client_id">'
                    f'{{"type":"string","value":"{_current_aid}"}}'
                    "</string>\n"
                    "</map>\n"
                )
                import tempfile as _tf_msys2
                _msys_tmp_dir = _tf_msys2.mkdtemp()
                _msys_local = os.path.join(_msys_tmp_dir, "msys-auth-data.xml")
                with open(_msys_local, 'w', encoding='utf-8') as _mf:
                    _mf.write(_msys_content)
                _msys_remote = "/data/local/tmp/msys-auth-data.xml"
                _msys_dest = "/data/data/com.facebook.katana/shared_prefs/msys-auth-data.xml"
                safe_subprocess_run(
                    [adb_path, "-s", device_id, "push", _msys_local, _msys_remote],
                    capture_output=True, text=True, timeout=10
                )
                adb_shell(
                    f'su -c "cp {_msys_remote} {_msys_dest} && rm -f {_msys_remote}"'
                )
                log(f"  msys-auth-data.xml written with rt_client_id={_current_aid}")
                shutil.rmtree(_msys_tmp_dir, ignore_errors=True)
            else:
                log(f"  could not get android_id for msys injection")
        except Exception as _msys_e:
            log(f"  Warning: msys injection error: {_msys_e}")

        # ── Step 6.7: Fix ownership on ALL Facebook data dirs ────────────
        # cp -rp preserves source permissions but source may be root-owned.
        # We must chown the entire tree including app_light_prefs and databases.
        log("Fixing ownership on Facebook data dirs...")
        _fb_uid_final = adb_shell(f'su -c "stat -c %u /data/data/com.facebook.katana"').strip()
        if not _fb_uid_final.isdigit():
            _fb_uid_final = "u0_a133"  # fallback known UID name
        _chown_result = adb_shell(
            f'su -c "chown -R {_fb_uid_final}:{_fb_uid_final} /data/data/com.facebook.katana && '
            f'chmod -R 771 /data/data/com.facebook.katana && '
            f'chmod 700 /data/data/com.facebook.katana/app_light_prefs/com.facebook.katana/ 2>/dev/null; '
            f'chmod 700 /data/data/com.facebook.katana/shared_prefs/ 2>/dev/null; '
            f'chmod 700 /data/data/com.facebook.katana/databases/ 2>/dev/null"',
            timeout=30
        )
        log(f"  chown result: {_chown_result[:100] or 'ok'}")

        # Verify a key session file ownership
        _sess_check = adb_shell(
            f'su -c "ls -la /data/data/com.facebook.katana/app_light_prefs/com.facebook.katana/ 2>/dev/null | head -5"'
        )
        log(f"  session files: {_sess_check[:200]}")

        # ── Step 6.8: Device identity already reset in Step 5.1 ──
        log("Device identity reset in Step 5.1 - Facebook will generate new device_id...")

        # ── Step 6.9: Register device with Facebook API ──────────────────
        # Call Facebook's Graph API to update the server-side device name
        # so "Where you're logged in" shows the correct spoofed identity.
        # This runs BEFORE launching Facebook so the server record is updated
        # before the app connects.
        log("Registering device identity with Facebook server...")
        try:
            from src.utils.fb_device_register import register_device_with_facebook
            _dev_xml_for_reg = _device_xml_for_api_reg
            if _dev_xml_for_reg and os.path.exists(_dev_xml_for_reg):
                _reg_ok, _reg_msg = register_device_with_facebook(
                    acc_folder=acc_folder,
                    uid=uid,
                    device_xml_path=_dev_xml_for_reg,
                    log_fn=lambda m: log(f"  {m}"),
                )
                log(f"  Registration: {'OK' if _reg_ok else 'FAILED'} — {_reg_msg[:100]}")
                # Clean up the persistent copy
                try:
                    shutil.rmtree(os.path.dirname(_dev_xml_for_reg), ignore_errors=True)
                except Exception:
                    pass
            else:
                log("  Device.xml not available for registration — skipping")
        except Exception as _reg_e:
            log(f"  Warning: device registration error: {_reg_e}")

        # Force stop Facebook again so it re-reads the new props
        adb_shell("am force-stop com.facebook.katana")
        adb_shell("am force-stop com.minsoftware.maxchanger")

        import time

        # Give processes time to fully die
        time.sleep(2)

        # Verify Device.xml is in place with correct content before launching
        _verify_xml = adb_shell(
            'su -c "cat /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml 2>/dev/null | head -3"'
        )
        log(f"  Device.xml on device: {_verify_xml[:100] or 'not found'}")

        # Launch Facebook — hook reads Device.xml at process start
        log("Launching Facebook...")

        # Force stop lite so it doesn't interfere with katana
        adb_shell("am force-stop com.facebook.lite")

        # Use LoginActivity — the actual registered launcher activity for katana
        # (MainActivity does not exist in newer Facebook versions)
        launch_r = safe_subprocess_run(
            [adb_path, "-s", device_id, "shell",
             "am", "start", "-n",
             "com.facebook.katana/.LoginActivity"],
            capture_output=True, text=True, timeout=15
        )
        launch_out = (launch_r.stdout + launch_r.stderr).strip()

        # Fallback: FbMainTabActivity
        if "Error" in launch_out or "Exception" in launch_out or "does not exist" in launch_out:
            log("  LoginActivity failed, trying FbMainTabActivity...")
            launch_r = safe_subprocess_run(
                [adb_path, "-s", device_id, "shell",
                 "am", "start", "-n",
                 "com.facebook.katana/.activity.FbMainTabActivity"],
                capture_output=True, text=True, timeout=15
            )
            launch_out = (launch_r.stdout + launch_r.stderr).strip()

        # Fallback: monkey on katana specifically
        if "Error" in launch_out or "Exception" in launch_out or "does not exist" in launch_out:
            log("  Trying monkey on katana...")
            launch_r = safe_subprocess_run(
                [adb_path, "-s", device_id, "shell",
                 "monkey", "-p", "com.facebook.katana", "-c",
                 "android.intent.category.LAUNCHER", "1"],
                capture_output=True, text=True, timeout=15
            )
            launch_out = (launch_r.stdout + launch_r.stderr).strip()

        log(f"  launch result: {launch_out[:80] if launch_out else 'ok'}")

        import time; time.sleep(2)

        # Verify katana is in foreground, not lite
        _fg = adb_shell("dumpsys activity activities | grep mResumedActivity").strip()
        log(f"  foreground: {_fg[:80]}")
        if "com.facebook.lite" in _fg:
            log("  WARNING: Lite in foreground — forcing katana...")
            adb_shell("am force-stop com.facebook.lite")
            time.sleep(1)
            safe_subprocess_run(
                [adb_path, "-s", device_id, "shell",
                 "am", "start", "-n", "com.facebook.katana/.LoginActivity"],
                capture_output=True, text=True, timeout=15
            )
            time.sleep(2)

        # ── Step 7.5: Verify fresh device_id generation (no sync wait needed) ──
        # Since we removed prefs_db, Facebook generates a fresh device_id with the
        # spoofed identity. The device name should show correctly IMMEDIATELY without
        # needing to wait for phone_id sync (even without Google Play Services).
        log("Verifying fresh device_id generation...")

        try:
            import tempfile as _tf75, os as _os75
            _sq_dir = _tf75.mkdtemp()
            _sq_path = _os75.path.join(_sq_dir, "fb_check.sh")
            _prefs_db_dev = "/data/data/com.facebook.katana/databases/prefs_db"
            with open(_sq_path, 'w', encoding='utf-8', newline='\n') as _f75:
                _f75.write("#!/system/bin/sh\n")
                _f75.write(f"sqlite3 {_prefs_db_dev} \"SELECT value FROM preferences WHERE key='/shared/device_id'\"\n")

            safe_subprocess_run(
                [adb_path, "-s", device_id, "push", _sq_path, "/data/local/tmp/fb_check.sh"],
                capture_output=True, text=True, timeout=10
            )
            adb_shell("chmod 755 /data/local/tmp/fb_check.sh")

            # Wait for Facebook to generate device_id (up to 30 seconds)
            _new_did = ""
            for _attempt in range(6):
                time.sleep(5)
                _check_out = adb_shell("su -c 'sh /data/local/tmp/fb_check.sh'", timeout=15).strip()
                _new_did = _check_out.strip()
                if _new_did and "-" in _new_did and len(_new_did) > 8:
                    break
                log(f"  waiting for device_id generation... ({(_attempt+1)*5}s)")
                # Keep Facebook active
                if _attempt > 0 and _attempt % 2 == 0:
                    adb_shell("am start -n com.facebook.katana/.LoginActivity", timeout=5)

            if _new_did and "-" in _new_did and len(_new_did) > 8:
                log(f"  ✓ Fresh device_id generated: {_new_did[:36]}")
                log(f"  ✓ Device name should show correctly immediately (no sync wait needed)!")
            else:
                log(f"  ⚠️  device_id not generated after 30s - may need manual Facebook restart")

            import shutil as _sh75
            _sh75.rmtree(_sq_dir, ignore_errors=True)
        except Exception as _e75:
            log(f"  Warning: verification error: {_e75}")

        # ── Step 8: Update account_info.json with current device ─────────
        # Record which device this account is now active on
        try:
            jp = os.path.join(acc_folder, "account_info.json")
            acc_info = {}
            if os.path.exists(jp):
                with open(jp, 'r', encoding='utf-8') as f:
                    acc_info = json.load(f)
            acc_info['device_serial'] = device_id
            acc_info['last_restored'] = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(jp, 'w', encoding='utf-8') as f:
                json.dump(acc_info, f, indent=2, ensure_ascii=False)
            log(f"  account_info.json updated: device_serial={device_id}")
        except Exception as e:
            log(f"  Warning: could not update account_info.json: {e}")

        # ── Step 9: Update device cache so Account tab shows correct assignment ──
        try:
            cache_file = os.path.join(__import__('tempfile').gettempdir(), "frt_device_cache.json")
            cache = {}
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
            # Store: uid → {device_serial, last_restored}
            cache[uid] = {
                'device_serial': device_id,
                'last_restored': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2)
            log(f"  device cache updated")
        except Exception as e:
            log(f"  Warning: could not update device cache: {e}")

        return True, "Session restored - check device"
    

    def stop_login_process(self):
        """Stop the login process"""
        self._stop_login_requested = True
        self.login_status_label.setText("Stopping...")
        self.login_status_label.setStyleSheet("QLabel { background-color: transparent; color: #888888; font-size: 12px; }")
    

    def submit_verification_code(self):
        """Submit verification code"""
        code = self.verification_code_input.text().strip()
        if not code:
            QMessageBox.warning(self, "No Code", "Please enter the verification code!")
            return
        
        # TODO: Implement verification code submission
        self.login_status_label.setText(f"✓ Verification code submitted: {code}")
        self.login_status_label.setStyleSheet("QLabel { background-color: #1e1e1e; color: #4CAF50; padding: 15px; border-radius: 0px; font-size: 13px; border: 1px solid #3a3a3a; }")
        
        # Hide verification inputs
        self.verification_code_label.setVisible(False)
        self.verification_code_input.setVisible(False)
        self.submit_code_btn.setVisible(False)
            
            
            
            
