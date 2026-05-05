"""
AccountMixin — Account Mixin methods.

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

import os, json, subprocess, threading, time, shutil, tempfile, re, requests

from src.i18n.engine import (
    translate as _T, register_widget as _reg,
    _CURRENT_LANG, _get_khmer_font, _REGISTRY as _I18N_REGISTRY,
)
from src.i18n.translations import TRANSLATIONS
from src.automation.url_normalizer import normalize_facebook_url, URL_TYPE_LABELS as _URL_TYPE_LABELS
from src.core.config import CONFIG_FILE
from src.core.subprocess_utils import safe_subprocess_run
# MaxChangeWorker lazy-imported in methods that use it (saves 75ms cold-start)
from src.ui.safe_combobox import SafeComboBox

# Project root — 3 levels up from src/ui/mixins/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class VPNProgressDialog(QDialog):
    """Custom non-modal progress dialog with loading animation"""
    def __init__(self, title, message, maximum, color_scheme="green", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)  # NON-MODAL - this is key!
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        
        # Color schemes
        colors = {
            "green": ("#4CAF50", "#45a049"),
            "blue": ("#2196F3", "#1976D2"),
            "red": ("#f44336", "#D32F2F")
        }
        color1, color2 = colors.get(color_scheme, colors["green"])
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Message label
        self.label = QLabel(message)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 13px;
                min-height: 40px;
            }
        """)
        layout.addWidget(self.label)
        
        # Progress bar - set to indeterminate (animated loading)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # 0 = indeterminate/animated mode
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                background: #252525;
                text-align: center;
                color: #cccccc;
                height: 28px;
                font-size: 12px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {color1}, stop:1 {color2});
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
        self.setMinimumWidth(450)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
            }
        """)
        
    def update_progress(self, value, text):
        """Update progress text (value ignored in animated mode)"""
        self.label.setText(text)
        QApplication.processEvents()  # Keep UI responsive


def _get_hidden_startupinfo():
    """Return a STARTUPINFO that hides the console window on Windows."""
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        return si
    except Exception:
        return None


def _parse_pipe_cookies(cookies_raw, d):
    """Parse pipe-delimited cookies field into (email, pass_mail, token, twofa, cookie).
    
    Supported formats:
      |Email|Pass/Mail|Token|2FA|Cookie   (5 parts after split)
      |Email|Pass/Mail|Token|Cookie       (4 parts — no 2FA)
      |Email|Pass/Mail|Cookie             (3 parts — no token/2FA)
    """
    _COOKIE_MARKERS = ('c_user=', 'xs=', 'datr=', 'fr=', 'sb=')

    def _is_cookie(s):
        return any(m in s for m in _COOKIE_MARKERS)

    def _is_token(s):
        # FB tokens typically start with M. or EAA or are long alphanumeric strings
        return s.startswith(('M.', 'EAA')) or (len(s) > 20 and not _is_cookie(s))

    parts = cookies_raw.split('|')
    # parts[0] is '' (before the leading |)
    email     = parts[1] if len(parts) > 1 else (d.get('email', '') or '—')
    pass_mail = parts[2] if len(parts) > 2 else (d.get('pass_mail', d.get('email_password', '—')) or '—')

    token = '—'; twofa = '—'; cookie = '—'

    if len(parts) > 3:
        p3 = parts[3]
        if _is_cookie(p3):
            # Format: |Email|Pass/Mail|Cookie  (no token, no 2FA)
            cookie = p3
        elif _is_token(p3):
            token = p3
            if len(parts) > 4:
                p4 = parts[4]
                if _is_cookie(p4):
                    # Format: |Email|Pass/Mail|Token|Cookie  (no 2FA)
                    cookie = p4
                else:
                    # Format: |Email|Pass/Mail|Token|2FA|Cookie
                    twofa = p4
                    cookie = parts[5] if len(parts) > 5 else '—'
            # else token only, no 2FA/cookie
        else:
            # Unknown — treat as token
            token = p3

    # Fallback to dedicated fields if still missing
    if token == '—': token = d.get('token', '') or '—'
    if twofa == '—': twofa = d.get('2fa') or d.get('twofa') or '—'
    if email == '—' or not email: email = d.get('email', '') or '—'
    if pass_mail == '—' or not pass_mail:
        pass_mail = d.get('pass_mail', d.get('email_password', '—')) or '—'

    return email or '—', pass_mail or '—', token, twofa, cookie


class AccountMixin:
    """Mixin — methods are injected into MainWindow via multiple inheritance."""
    
    def _update_vpn_progress(self, value, text):
        """Update VPN progress dialog (called via signal from background thread)"""
        if hasattr(self, '_current_vpn_progress') and self._current_vpn_progress:
            try:
                self._current_vpn_progress.setValue(value)
                self._current_vpn_progress.setLabelText(text)
                QApplication.processEvents()  # Keep UI responsive
            except:
                pass

    def open_account_tab(self):
        """Open the Account & Devices tab - recreates it if needed"""
        # Check if Account tab already exists in tab widget
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Accounts and Devices":
                self.tab_widget.setCurrentIndex(i)
                self.load_main_account_tab()
                return
        
        # Tab doesn't exist - check if we need to recreate it
        widget_valid = False
        if hasattr(self, 'main_account_tab') and self.main_account_tab is not None:
            try:
                # Test if widget is still valid
                self.main_account_tab.isVisible()
                widget_valid = True
            except RuntimeError:
                # Widget was deleted - need to recreate
                widget_valid = False
        
        if not widget_valid:
            # Recreate the tab widget
            self._create_account_tab_widget()
        
        # Add the tab
        self.account_tab_index = self.tab_widget.addTab(self.main_account_tab, "Accounts and Devices")
        self.tab_widget.setCurrentIndex(self.account_tab_index)
        
        # Add close button
        account_close_btn = QPushButton("×")
        account_close_btn.setFixedSize(20, 20)
        account_close_btn.setStyleSheet("""
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
        account_close_btn.clicked.connect(self.close_main_account_tab)
        self.tab_widget.tabBar().setTabButton(self.account_tab_index, QTabBar.ButtonPosition.RightSide, account_close_btn)
        
        # Defer load slightly so the tab widget fully renders before populating
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.load_main_account_tab)


    def _create_account_tab_widget(self):
        """Create the Account & Devices tab widget - can be called to recreate if deleted"""
        # No parent here — addTab will reparent it into the tab stack.
        # Passing `self` as parent caused the widget to briefly appear as a
        # floating child of MainWindow before addTab reparented it.
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


    def open_accounts_only_tab(self):
        """Open a tab showing only the accounts table (no devices)"""
        # Check if Accounts tab already exists
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Accounts":
                self.tab_widget.setCurrentIndex(i)
                # Refresh the data
                if hasattr(self, '_accounts_only_table'):
                    self._load_accounts_only_table(self._accounts_only_table)
                return
        
        # Create new accounts-only tab
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QHeaderView, QLineEdit, QComboBox, QPushButton, QHBoxLayout, QSplitter, QLabel
        from PyQt6.QtCore import Qt
        
        accounts_only_tab = QWidget()
        accounts_only_tab.setStyleSheet("background-color: #1e1e1e;")
        layout = QVBoxLayout(accounts_only_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #2d2d2d; border-bottom: 1px solid #3d3d3d;")
        toolbar.setFixedHeight(50)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(15, 0, 15, 0)
        
        # Search and filters (reuse existing ones or create new)
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search...")
        search_input.setFixedHeight(32)
        search_input.setFixedWidth(160)
        search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #4CAF50; }
            QLineEdit:hover { border-color: #4CAF50; }
        """)
        toolbar_layout.addWidget(search_input)

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
        category_filter = SafeComboBox()
        category_filter.addItems(["All", "Email", "Phone", "---"])
        for cat in self.load_custom_categories():
            category_filter.addItem(cat)
        category_filter.setStyleSheet(_combo_style)
        toolbar_layout.addWidget(category_filter)
        
        # Store reference for later updates
        self._accounts_only_category_filter = category_filter

        # Status filter
        status_filter = SafeComboBox()
        status_filter.addItems(["All Status", "Active", "Pending", "Suspended", "Checkpoint"])
        status_filter.setStyleSheet(_combo_style)
        toolbar_layout.addWidget(status_filter)

        toolbar_layout.addStretch()

        # Compact stats display
        accounts_count_label = QLabel("10 accounts")
        accounts_count_label.setStyleSheet("color: #888888; font-size: 11px; padding: 0 8px;")
        toolbar_layout.addWidget(accounts_count_label)
        
        accounts_selected_label = QLabel("0 selected")
        accounts_selected_label.setStyleSheet("color: #4CAF50; font-size: 11px; padding: 0 8px;")
        toolbar_layout.addWidget(accounts_selected_label)
        
        devices_count_label = QLabel("0 devices")
        devices_count_label.setStyleSheet("color: #888888; font-size: 11px; padding: 0 8px;")
        toolbar_layout.addWidget(devices_count_label)
        
        devices_selected_label = QLabel("0 selected")
        devices_selected_label.setStyleSheet("color: #4CAF50; font-size: 11px; padding: 0 8px;")
        toolbar_layout.addWidget(devices_selected_label)
        
        layout.addWidget(toolbar)
        
        # Create horizontal splitter for left sidebar and main content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #1e1e1e;
                width: 8px;
            }
            QSplitter::handle:hover {
                background-color: #4CAF50;
            }
        """)
        
        # Left sidebar - Device table
        left_panel = QWidget()
        left_panel.setStyleSheet("background-color: #2d2d2d;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Device table
        device_table = QTableWidget()
        device_table.setColumnCount(5)
        device_table.setHorizontalHeaderLabels(["#", "Device Name", "Proxy", "Device Changer", "Status"])
        device_table.setStyleSheet("""
            QTableWidget {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: none;
                gridline-color: #3d3d3d;
                selection-background-color: rgba(76, 175, 80, 0.3);
                outline: none;
            }
            QTableWidget::item {
                padding: 8px 5px;
                border-bottom: 1px solid #3d3d3d;
                font-size: 12px;
                outline: none;
            }
            QTableWidget::item:selected {
                background-color: rgba(76, 175, 80, 0.3);
                color: #ffffff;
                outline: none;
            }
            QTableWidget::item:focus {
                outline: none;
                border: none;
            }
            QHeaderView::section {
                background-color: #363636;
                color: #888888;
                padding: 10px 8px;
                border: none;
                border-bottom: 2px solid #4CAF50;
                border-right: 1px solid #3d3d3d;
                font-size: 11px;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QHeaderView::section:first {
                border-left: none;
            }
            QHeaderView::section:last {
                border-right: none;
            }
            QScrollBar:horizontal {
                border: none;
                background: #2d2d2d;
                height: 12px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #555555;
                min-width: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #4CAF50;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar:vertical {
                border: none;
                background: #2d2d2d;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4CAF50;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        device_header_view = device_table.horizontalHeader()
        device_header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        device_table.setColumnWidth(0, 40)
        for i in range(1, 5):
            device_header_view.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        # Enable horizontal scrolling
        device_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        device_table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        device_table.horizontalScrollBar().setSingleStep(10)
        device_table.horizontalScrollBar().setPageStep(100)
        
        device_table.verticalHeader().setVisible(False)
        device_table.verticalHeader().setDefaultSectionSize(36)
        device_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        device_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        device_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        device_table.setShowGrid(False)
        device_table.setAlternatingRowColors(False)
        device_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        # Store last clicked row for toggle behavior
        device_table._last_clicked_row = None
        
        # Enable toggle selection - click to select, click again to deselect
        def device_mouse_press(event):
            from PyQt6.QtCore import Qt as _Qt
            if event.button() == _Qt.MouseButton.LeftButton:
                idx = device_table.indexAt(event.pos())
                if idx.isValid():
                    row = idx.row()
                    # Check if this row is already selected
                    if device_table.selectionModel().isRowSelected(row, device_table.rootIndex()):
                        # If clicking the same row again, deselect it
                        if device_table._last_clicked_row == row:
                            device_table.clearSelection()
                            device_table._last_clicked_row = None
                            event.accept()
                            return
                    device_table._last_clicked_row = row
            QTableWidget.mousePressEvent(device_table, event)
        
        device_table.mousePressEvent = device_mouse_press
        
        left_layout.addWidget(device_table)
        
        # Right panel - Accounts table
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: #1e1e1e;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # Create accounts table (copy from main account table)
        accounts_table = QTableWidget()
        accounts_table.setColumnCount(29)
        accounts_table.setHorizontalHeaderLabels([
            "#", "UID", "Password", "Current Status", "Email", "Phone", "Name",
            "Pass/Mail", "Token", "Cookie", "2FA", "Created", "Category",
            "Status", "Device Info", "Page", "Primary", "Sex", "DOB",
            "Old Mail", "Avatar", "Cover", "Friend & Follower", "Last Status",
            "Group", "Group ID", "Group Name", "FB-App"
        ])
        
        # Apply the same stylesheet as the main account table
        accounts_table.setStyleSheet("""
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
        
        # Copy header settings
        header = accounts_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        accounts_table.setColumnWidth(0, 50)
        for i in range(1, 29):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        # Enable horizontal scrolling
        accounts_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        accounts_table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        accounts_table.horizontalScrollBar().setSingleStep(10)
        accounts_table.horizontalScrollBar().setPageStep(100)
        
        accounts_table.verticalHeader().setVisible(False)
        accounts_table.verticalHeader().setDefaultSectionSize(44)
        accounts_table.setSortingEnabled(False)
        accounts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        accounts_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        accounts_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        accounts_table.setShowGrid(False)
        accounts_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        accounts_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        accounts_table.customContextMenuRequested.connect(self.show_account_context_menu)
        
        # Store last clicked row for toggle behavior
        accounts_table._last_clicked_row = None
        
        # Enable toggle selection - click to select, click again to deselect
        def accounts_mouse_press(event):
            from PyQt6.QtCore import Qt as _Qt
            if event.button() == _Qt.MouseButton.LeftButton:
                idx = accounts_table.indexAt(event.pos())
                if idx.isValid():
                    row = idx.row()
                    # Check if this row is already selected
                    if accounts_table.selectionModel().isRowSelected(row, accounts_table.rootIndex()):
                        # If clicking the same row again, deselect it
                        if accounts_table._last_clicked_row == row:
                            accounts_table.clearSelection()
                            accounts_table._last_clicked_row = None
                            event.accept()
                            return
                    accounts_table._last_clicked_row = row
            QTableWidget.mousePressEvent(accounts_table, event)
        
        accounts_table.mousePressEvent = accounts_mouse_press
        
        right_layout.addWidget(accounts_table)
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 900])  # Left panel 300px, right panel takes rest
        
        layout.addWidget(splitter)
        
        # Store reference to tables and labels for refreshing
        self._accounts_only_table = accounts_table
        self._accounts_only_device_table = device_table
        self._accounts_count_label = accounts_count_label
        self._accounts_selected_label = accounts_selected_label
        self._devices_count_label = devices_count_label
        self._devices_selected_label = devices_selected_label
        
        # Update selection counts
        def update_accounts_selection():
            selected_count = len(accounts_table.selectionModel().selectedRows())
            total_count = accounts_table.rowCount()
            accounts_count_label.setText(f"{total_count} accounts")
            accounts_selected_label.setText(f"{selected_count} selected")
        
        def update_devices_selection():
            selected_count = len(device_table.selectionModel().selectedRows())
            total_count = device_table.rowCount()
            devices_count_label.setText(f"{total_count} devices")
            devices_selected_label.setText(f"{selected_count} selected")
        
        accounts_table.itemSelectionChanged.connect(update_accounts_selection)
        device_table.itemSelectionChanged.connect(update_devices_selection)

        # Wire search + filter signals
        def _apply_accounts_only_filter():
            search = search_input.text().lower()
            cat = category_filter.currentText()
            stat = status_filter.currentText()
            visible = 0
            for row in range(accounts_table.rowCount()):
                show = True
                if search:
                    uid   = (accounts_table.item(row, 1) or QTableWidgetItem()).text().lower()
                    email = (accounts_table.item(row, 3) or QTableWidgetItem()).text().lower()
                    phone = (accounts_table.item(row, 4) or QTableWidgetItem()).text().lower()
                    name  = (accounts_table.item(row, 5) or QTableWidgetItem()).text().lower()
                    if search not in uid and search not in email and search not in phone and search not in name:
                        show = False
                if show and cat not in ("All", "---"):
                    uid_val = (accounts_table.item(row, 1) or QTableWidgetItem()).text()
                    m = getattr(self, '_account_meta_cache', {}).get(uid_val, {})
                    if cat == "Email":
                        show = m.get('signup_method', 'email') == 'email'
                    elif cat == "Phone":
                        show = m.get('signup_method', 'email') == 'phone'
                    else:
                        show = m.get('category', '') == cat
                if show and stat != "All Status":
                    cur_status = (accounts_table.item(row, 2) or QTableWidgetItem()).text().lower()
                    show = stat.lower() in cur_status
                accounts_table.setRowHidden(row, not show)
                if not accounts_table.isRowHidden(row):
                    visible += 1
            accounts_count_label.setText(f"{visible} accounts")

        search_input.textChanged.connect(lambda _: _apply_accounts_only_filter())
        category_filter.currentTextChanged.connect(lambda _: _apply_accounts_only_filter())
        status_filter.currentTextChanged.connect(lambda _: _apply_accounts_only_filter())
        
        # Add tab
        accounts_only_tab_index = self.tab_widget.addTab(accounts_only_tab, "Accounts")
        self.tab_widget.setCurrentIndex(accounts_only_tab_index)
        
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
        close_btn.clicked.connect(lambda: self._close_accounts_only_tab(accounts_only_tab_index))
        self.tab_widget.tabBar().setTabButton(accounts_only_tab_index, QTabBar.ButtonPosition.RightSide, close_btn)
        
        # Load account data into the table
        self._load_accounts_only_table(accounts_table)
        
        # Auto-load devices when tab is opened
        self._load_devices_only_table(device_table)
        
        # Update counts after loading
        update_accounts_selection()
        update_devices_selection()
    
    
    def _close_accounts_only_tab(self, tab_index):
        """Close the accounts-only tab"""
        # Find the tab by name to ensure we're closing the right one
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Accounts":
                self.tab_widget.removeTab(i)
                if hasattr(self, '_accounts_only_table'):
                    delattr(self, '_accounts_only_table')
                return
    
    
    def _load_devices_only_table(self, table):
        """Load device data into the devices-only table"""
        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtGui import QColor
        from PyQt6.QtCore import Qt
        import tempfile

        table.setRowCount(0)

        cgr = QColor("#4CAF50")
        cgo = QColor("#FF9800")
        cg  = QColor("#888888")

        # Use the same device source as the main account tab
        device_ids = []
        if hasattr(self, 'device_checkboxes') and self.device_checkboxes:
            for cb in self.device_checkboxes:
                try:
                    if cb.isChecked():
                        device_ids.append(cb.text())
                except RuntimeError:
                    pass
        if not device_ids and hasattr(self, '_checked_device_ids'):
            device_ids = list(self._checked_device_ids)

        # If still empty, fall back to live ADB scan
        if not device_ids:
            try:
                result = subprocess.run(
                    [self.adb_path, 'devices'],
                    capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=5
                )
                for line in result.stdout.strip().split('\n')[1:]:
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[1] == 'device':
                        device_ids.append(parts[0])
            except Exception:
                pass

        # Load proxy cache
        proxy_cache = {}
        try:
            cf = os.path.join(tempfile.gettempdir(), "frt_device_proxy_cache.json")
            if os.path.exists(cf):
                with open(cf, 'r', encoding='utf-8') as f:
                    proxy_cache = json.load(f)
        except Exception:
            pass

        # Load spoof cache for device name
        spoof_cache = {}
        try:
            sf = os.path.join(tempfile.gettempdir(), "frt_device_spoof_cache.json")
            if os.path.exists(sf):
                with open(sf, 'r', encoding='utf-8') as f:
                    spoof_cache = json.load(f)
        except Exception:
            pass

        for row_idx, device_id in enumerate(device_ids):
            row = table.rowCount()
            table.insertRow(row)
            table.setRowHeight(row, 36)

            device_name = spoof_cache.get(device_id, device_id)
            proxy = proxy_cache.get(device_id, '—')
            device_changer = "Enabled" if hasattr(self, 'enable_device_changer_checkbox') and self.enable_device_changer_checkbox.isChecked() else "—"

            i0 = QTableWidgetItem(str(row_idx + 1)); i0.setForeground(cg); i0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            i1 = QTableWidgetItem(device_name); i1.setForeground(cgr)
            i2 = QTableWidgetItem(proxy); i2.setForeground(cgo if proxy != '—' else cg)
            i3 = QTableWidgetItem(device_changer); i3.setForeground(cgr if device_changer == "Enabled" else cg)

            table.setItem(row, 0, i0)
            table.setItem(row, 1, i1)
            table.setItem(row, 2, i2)
            table.setItem(row, 3, i3)

        if hasattr(self, '_devices_count_label'):
            self._devices_count_label.setText(f"{len(device_ids)} devices")
    
    
    def _load_accounts_only_table(self, table):
        """Load account data into the accounts-only table — I/O in background thread."""
        import threading as _threading

        def _gather():
            from PyQt6.QtWidgets import QTableWidgetItem
            from PyQt6.QtGui import QColor
            from PyQt6.QtCore import Qt

            cgr = QColor("#4CAF50"); cgo = QColor("#FF9800"); cg = QColor("#888888")
            rows = []
            backup_path = os.path.join(_PROJECT_ROOT, "account_backup")
            if os.path.exists(backup_path):
                for folder_name in os.listdir(backup_path):
                    folder_path = os.path.join(backup_path, folder_name)
                    if os.path.isdir(folder_path):
                        jp = os.path.join(folder_path, "account_info.json")
                        if os.path.exists(jp):
                            try:
                                with open(jp, 'r', encoding='utf-8') as f:
                                    d = json.load(f)
                                uid = d.get('account_uid', d.get('uid', d.get('id', folder_name.split('_')[0])))
                                d['uid'] = uid
                                rows.append(d)
                            except: pass

            from PyQt6.QtCore import QMetaObject, Qt as _Qt
            # Pass rows to main thread via closure
            self._accounts_only_pending_rows = rows
            QMetaObject.invokeMethod(self, "_apply_accounts_only_table_rows", _Qt.ConnectionType.QueuedConnection)

        _threading.Thread(target=_gather, daemon=True).start()

    @pyqtSlot()
    def _apply_accounts_only_table_rows(self):
        """Apply gathered account rows to the accounts-only table on the main thread."""
        table = getattr(self, '_accounts_only_table', None)
        rows = getattr(self, '_accounts_only_pending_rows', [])
        if not table or not rows:
            return
        try:
            table.objectName()
        except RuntimeError:
            return

        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtGui import QColor
        from PyQt6.QtCore import Qt

        cgr = QColor("#4CAF50"); cgo = QColor("#FF9800"); cg = QColor("#888888")
        table.setRowCount(0)

        for row_idx, d in enumerate(rows):
            row = table.rowCount()
            table.insertRow(row)
            table.setRowHeight(row, 36)
            uid = d.get('uid', '')
            password = d.get('password', '—')
            current_status = d.get('current_status', d.get('account_status', '—')) or '—'

            cookies_raw = d.get('cookies', '') or d.get('cookie', '')
            if cookies_raw and cookies_raw.startswith('|'):
                email, pass_mail, token, twofa, cookie = _parse_pipe_cookies(cookies_raw, d)
            else:
                email = d.get('email', '') or '—'
                pass_mail = d.get('pass_mail', d.get('email_password', '—')) or '—'
                token = d.get('token', '') or '—'
                twofa = d.get('2fa') or d.get('twofa') or '—'
                cookie = cookies_raw if cookies_raw else '—'

            phone = d.get('phone', '') or '—'
            name = d.get('full_name', (d.get('first_name','') + ' ' + d.get('last_name','')).strip()) or '—'
            token_display = token[:10] + '...' if token != '—' and len(token) > 10 else token
            cookie_display = cookie[:10] + '...' if cookie != '—' and len(cookie) > 10 else cookie
            created = d.get('created_at', d.get('created_date', '—')) or '—'
            category = d.get('category', '—') or '—'
            status = d.get('status', '—') or '—'
            device_info = d.get('device_info', {})
            device_model = device_info.get('model', '—') if isinstance(device_info, dict) else '—'
            page = d.get('page', '—') or '—'
            primary = d.get('primary', '—') or '—'
            sex = d.get('gender', d.get('sex', '—')) or '—'
            dob = d.get('birthday', d.get('dob', '—')) or '—'
            old_mail = d.get('old_mail', d.get('old_email', '—')) or '—'
            avatar = d.get('avatar', d.get('profile_pic', '—')) or '—'
            avatar_display = avatar[:15] + '...' if avatar != '—' and len(avatar) > 15 else avatar
            cover = d.get('cover', d.get('cover_photo', '—')) or '—'
            cover_display = cover[:15] + '...' if cover != '—' and len(cover) > 15 else cover
            friend_follower = d.get('friend_follower', d.get('friends', '—')) or '—'
            last_status = d.get('last_status', '—') or '—'
            group = d.get('group', '—') or '—'
            group_id = d.get('group_id', '—') or '—'
            group_name = d.get('group_name', '—') or '—'
            fb_app = d.get('fb_app', d.get('app', '—')) or '—'

            rn = QTableWidgetItem(str(row_idx+1)); rn.setForeground(cg); rn.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            i0 = QTableWidgetItem(uid); i0.setForeground(cgr)
            i1 = QTableWidgetItem(password)
            i2 = QTableWidgetItem(current_status)
            if current_status.lower() in ['active', 'live', 'working']: i2.setForeground(cgr)
            elif current_status.lower() in ['checkpoint', 'locked', 'disabled']: i2.setForeground(QColor("#f44336"))
            elif current_status.lower() in ['pending', 'review']: i2.setForeground(cgo)
            else: i2.setForeground(cg)
            i3 = QTableWidgetItem(email if email != '—' else phone); i3.setForeground(cg if email == '—' and phone == '—' else cgr)
            i4 = QTableWidgetItem(phone if phone != '—' else '—')
            i5 = QTableWidgetItem(name)
            i6 = QTableWidgetItem(pass_mail)
            i7 = QTableWidgetItem(token_display); i7.setForeground(cgr if token != "—" else cg)
            if token != '—': i7.setToolTip(token)
            i8 = QTableWidgetItem(cookie_display); i8.setForeground(cgr if cookie != "—" else cg)
            if cookie != '—': i8.setToolTip(cookie)
            i9 = QTableWidgetItem(twofa); i9.setForeground(cgo if twofa != "—" else cg)
            i10 = QTableWidgetItem(created)
            i11 = QTableWidgetItem(category); i11.setForeground(cgr if category != "—" else cg)
            i12 = QTableWidgetItem(status); i12.setForeground(cgr if status == "active" else cgo)
            i13 = QTableWidgetItem(device_model)
            i14 = QTableWidgetItem(page); i15 = QTableWidgetItem(primary); i16 = QTableWidgetItem(sex)
            i17 = QTableWidgetItem(dob); i18 = QTableWidgetItem(old_mail)
            i19 = QTableWidgetItem(avatar_display)
            if avatar != '—': i19.setToolTip(avatar)
            i20 = QTableWidgetItem(cover_display)
            if cover != '—': i20.setToolTip(cover)
            i21 = QTableWidgetItem(friend_follower); i22 = QTableWidgetItem(last_status)
            i23 = QTableWidgetItem(group); i24 = QTableWidgetItem(group_id)
            i25 = QTableWidgetItem(group_name); i26 = QTableWidgetItem(fb_app)

            table.setItem(row, 0, rn)
            for col, item in enumerate([i0,i1,i2,i3,i4,i5,i6,i7,i8,i9,i10,i11,i12,i13,i14,i15,i16,i17,i18,i19,i20,i21,i22,i23,i24,i25,i26], start=1):
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row, col, item)

        if hasattr(self, '_accounts_count_label'):
            self._accounts_count_label.setText(f"{len(rows)} accounts")
    

    def load_main_account_tab(self):
        """Load devices into the main account tab (device-centric view)"""
        # Guard: only load if the account tab widgets exist
        if not hasattr(self, 'account_table') or not hasattr(self, 'devices_table'):
            return
        try:
            self.account_table.objectName()  # Will raise if deleted
            self.devices_table.objectName()
        except RuntimeError:
            return
        self.load_devices_in_account_table()
        self.update_account_stats()

        # Also refresh the "Accounts" only tab if it's open
        if hasattr(self, '_accounts_only_table'):
            try:
                self._accounts_only_table.objectName()
                self._load_accounts_only_table(self._accounts_only_table)
                if hasattr(self, '_accounts_count_label'):
                    self._accounts_count_label.setText(f"{self._accounts_only_table.rowCount()} accounts")
            except RuntimeError:
                pass
    

    def auto_load_devices_to_account_tab(self):
        """Load devices by calling the main refresh_devices which syncs everything"""
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self.refresh_devices)
    
    
    def _auto_load_devices_on_startup(self):
        """Auto load devices on startup if enabled in settings"""
        from src.core.config import load_config
        config = load_config()
        if config.get('auto_load_device', False):
            from PyQt6.QtCore import QTimer
            def _do_load():
                self.add_activity("✓ Auto loading devices...")
                # refresh_devices populates device_checkboxes so any tab opened
                # later will already have device data ready
                self.refresh_devices()
                QTimer.singleShot(1500, self.load_dashboard_statistics)

            # Always just load — no need to open the tab
            # The tab will show devices when the user opens it because
            # device_checkboxes will already be populated
            QTimer.singleShot(0, _do_load)
    

    def load_devices_in_account_table(self):
        """Load accounts and devices - I/O in background, UI update on main thread."""
        import threading, tempfile

        # Read checkbox state on main thread BEFORE going to background
        # Use _checked_device_ids as the authoritative source — it's a plain Python list
        # that survives checkbox deleteLater() cycles
        checked_devices = []
        if hasattr(self, 'device_checkboxes') and self.device_checkboxes:
            for cb in self.device_checkboxes:
                try:
                    if cb.isChecked():
                        checked_devices.append(cb.text())
                except RuntimeError:
                    pass  # widget was deleted — skip

        # Fallback to cached list if checkboxes are gone/empty
        if not checked_devices and hasattr(self, '_checked_device_ids'):
            checked_devices = list(self._checked_device_ids)

        def _gather():
            # Sync 效卫 device order first if available
            self._sync_xiaowei_device_order()

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

            device_mappings = {}
            try:
                mf = os.path.join(tempfile.gettempdir(), "frt_device_account_mapping.json")
                if os.path.exists(mf):
                    with open(mf, 'r', encoding='utf-8') as f: device_mappings = json.load(f)
            except: pass

            # ADB call (the slow part)
            connected_devices = set()
            try:
                r = subprocess.run([self.adb_path, "devices"], capture_output=True, text=True, timeout=5)
                for line in r.stdout.splitlines()[1:]:
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[1] == "device":
                        connected_devices.add(parts[0])
            except: pass

            # Read account backup files
            accounts_dict = {}
            backup_path = os.path.join(_PROJECT_ROOT, "account_backup")
            if os.path.exists(backup_path):
                for folder_name in os.listdir(backup_path):
                    folder_path = os.path.join(backup_path, folder_name)
                    if os.path.isdir(folder_path):
                        jp = os.path.join(folder_path, "account_info.json")
                        if os.path.exists(jp):
                            try:
                                with open(jp, 'r', encoding='utf-8') as f:
                                    d = json.load(f)
                                    uid = d.get('account_uid', d.get('uid', d.get('id', folder_name.split('_')[0])))
                                    d['uid'] = uid
                                    d['folder'] = folder_name
                                    accounts_dict[folder_name] = d
                            except: pass

            # Check which devices have scrcpy screen view open
            screen_devices = set()
            try:
                import psutil as _psutil
                for proc in _psutil.process_iter(['name', 'cmdline']):
                    try:
                        if proc.info['name'] and 'scrcpy' in proc.info['name'].lower():
                            cmdline = ' '.join(proc.info['cmdline'] or [])
                            for dev_id in checked_devices:
                                if dev_id in cmdline:
                                    screen_devices.add(dev_id)
                    except: pass
            except: pass

            # Build devices list from pre-read checkbox data
            # Fetch models in parallel for all unknown devices
            import concurrent.futures as _cf
            def _get_model(dev_id):
                try:
                    r = subprocess.run([self.adb_path, "-s", dev_id, "shell",
                        "getprop ro.product.model"],
                        capture_output=True, text=True, timeout=3)
                    return dev_id, r.stdout.strip() or 'Unknown'
                except:
                    return dev_id, 'Unknown'

            # Determine which devices need model lookup
            need_model = [d for d in checked_devices
                         if d not in device_mappings or device_mappings[d].get('model','Unknown') == 'Unknown']
            model_cache = {}
            if need_model:
                with _cf.ThreadPoolExecutor(max_workers=len(need_model)) as ex:
                    for dev_id, model in ex.map(_get_model, need_model):
                        model_cache[dev_id] = model

            devices_list = []
            for device_id in checked_devices:
                if connected_devices and device_id not in connected_devices:
                    continue
                fake_device = spoof_cache.get(device_id, "—")
                if device_id in device_mappings:
                    m = device_mappings[device_id]
                    model = m.get('model', 'Unknown')
                    if model == 'Unknown':
                        model = model_cache.get(device_id, 'Unknown')
                    assigned_uid = m.get('uid', '—')
                else:
                    model = model_cache.get(device_id, 'Unknown')
                    assigned_uid = '—'
                viewing = device_id in screen_devices
                status = ('Active 📺' if viewing else 'Active') if assigned_uid != '—' else ('Viewing 📺' if viewing else 'Idle')
                devices_list.append({'device_id': device_id, 'model': model,
                    'status': status, 'assigned_uid': assigned_uid, 'fake_device': fake_device})

            try:
                nf = os.path.join(tempfile.gettempdir(), "frt_device_numbers.json")
                if os.path.exists(nf):
                    with open(nf, 'r', encoding='utf-8') as f: nums = json.load(f)
                    devices_list.sort(key=lambda d: nums.get(d['device_id'], 9999))
            except: pass

            self._load_table_signal.emit(accounts_dict, devices_list, proxy_cache)

        threading.Thread(target=_gather, daemon=True).start()


    def _on_show_dialog(self, title, message):
        """Show info dialog on main thread via signal."""
        QMessageBox.information(self, title, message)


    def _on_load_table_data(self, accounts_dict, devices_list, proxy_cache):
        """Called on main thread via signal to update tables."""
        for attr in ('account_table', 'devices_table'):
            if not hasattr(self, attr): return
            try: getattr(self, attr).objectName()
            except RuntimeError: return

        self.account_table.setSortingEnabled(False)
        self.devices_table.setSortingEnabled(False)
        self.account_table.clearContents(); self.account_table.setRowCount(0)
        self.devices_table.clearContents(); self.devices_table.setRowCount(0)

        # Build in-memory meta cache for filter_main_account_tab (no disk I/O on filter)
        self._account_meta_cache = {
            d.get('uid', ''): {
                'category': d.get('category', ''),
                'signup_method': d.get('signup_method', 'email'),
            }
            for d in accounts_dict.values() if d.get('uid')
        }

        cg = QColor("#888888"); cgr = QColor("#4CAF50")
        cgo = QColor("#FFD700"); cor = QColor("#FF9800")

        for row_idx, (_, d) in enumerate(accounts_dict.items()):
            row = self.account_table.rowCount()
            self.account_table.insertRow(row)
            self.account_table.setRowHeight(row, 36)
            uid      = d.get('uid', '')
            password = d.get('password', '—')
            
            # Parse cookies field if it contains pipe-delimited data
            cookies_raw = d.get('cookies', '') or d.get('cookie', '')
            if cookies_raw and cookies_raw.startswith('|'):
                email, pass_mail, token, twofa, cookie = _parse_pipe_cookies(cookies_raw, d)
            else:
                email = d.get('email', '') or '—'
                pass_mail = d.get('pass_mail', d.get('email_password', '—')) or '—'
                token = d.get('token', '') or '—'
                twofa = d.get('2fa') or d.get('twofa') or '—'
                cookie = cookies_raw if cookies_raw else '—'
            
            phone    = d.get('phone', '') or '—'
            name     = d.get('full_name', (d.get('first_name','') + ' ' + d.get('last_name','')).strip()) or '—'
            
            # Truncate token to first 10 characters for display
            if token != '—' and len(token) > 10:
                token_display = token[:10] + '...'
            else:
                token_display = token
            
            # Truncate cookie to first 10 characters for display
            if cookie != '—' and len(cookie) > 10:
                cookie_display = cookie[:10] + '...'
            else:
                cookie_display = cookie
            
            created  = d.get('created_at', d.get('created_date', '—')) or '—'
            category = d.get('category', '—') or '—'

            rn = QTableWidgetItem(str(row_idx+1)); rn.setForeground(cg)
            rn.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            rn.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            i0 = QTableWidgetItem(uid);       i0.setForeground(cgr)
            i1 = QTableWidgetItem(password)
            i2 = QTableWidgetItem(email if email != '—' else phone)
            i2.setForeground(cg if email == '—' and phone == '—' else cgr)
            i3 = QTableWidgetItem(phone if phone != '—' else '—')
            i4 = QTableWidgetItem(name)
            i5 = QTableWidgetItem(pass_mail)
            i6 = QTableWidgetItem(token_display);    i6.setForeground(cgr if token != "—" else cg)
            # Store full token in tooltip
            if token != '—':
                i6.setToolTip(token)
            i7 = QTableWidgetItem(cookie_display);    i7.setForeground(cgr if cookie != "—" else cg)
            # Store full cookie in tooltip for reference
            if cookie != '—':
                i7.setToolTip(cookie)
            i8 = QTableWidgetItem(twofa);     i8.setForeground(cgo if twofa != "—" else cg)
            i9 = QTableWidgetItem(created)
            i10 = QTableWidgetItem(category);  i10.setForeground(cgr if category != "—" else cg)
            self.account_table.setItem(row, 0, rn)
            for col, item in enumerate([i0,i1,i2,i3,i4,i5,i6,i7,i8,i9,i10], start=1):
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.account_table.setItem(row, col, item)

        for row in range(self.devices_table.rowCount()):
            for col in range(self.devices_table.columnCount()):
                self.devices_table.setSpan(row, col, 1, 1)

        if devices_list:
            for di, dd in enumerate(devices_list):
                row = self.devices_table.rowCount()
                self.devices_table.insertRow(row)
                self.devices_table.setRowHeight(row, 36)
                proxy = proxy_cache.get(dd['device_id'], '—')
                rn = QTableWidgetItem(str(di+1)); rn.setForeground(cg)
                rn.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                rn.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                i0 = QTableWidgetItem(dd['device_id']);    i0.setForeground(cgr)
                i1 = QTableWidgetItem(dd['model'])
                i2 = QTableWidgetItem(proxy);              i2.setForeground(cor if proxy != '—' else cg)
                i3 = QTableWidgetItem(dd['status']);       i3.setForeground(cgr if dd['status'] == "Active" else cg)
                i4 = QTableWidgetItem(dd['assigned_uid']); i4.setForeground(cgo if dd['assigned_uid'] != '—' else cg)
                i5 = QTableWidgetItem(dd['fake_device']);  i5.setForeground(cor if dd['fake_device'] != '—' else cg)
                self.devices_table.setItem(row, 0, rn)
                for col, item in enumerate([i0,i1,i2,i3,i4,i5], start=1):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self.devices_table.setItem(row, col, item)
        else:
            self.devices_table.insertRow(0)
            self.devices_table.setRowHeight(0, 150)
            empty = QTableWidgetItem("\n\nNo devices loaded\n\nClick 'Load Devices' button above\nto select devices")
            empty.setForeground(QColor("#888888"))
            empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.devices_table.setItem(0, 0, empty)
            self.devices_table.setSpan(0, 0, 1, 7)

        self.add_activity(f"Loaded {len(accounts_dict)} accounts, {len(devices_list)} devices")
        if hasattr(self, 'acct_total_label'): self.acct_total_label.setText(f"{len(accounts_dict)} accounts")
        if hasattr(self, 'dev_total_label'):  self.dev_total_label.setText(f"{len(devices_list)} devices")
        self.account_table.setUpdatesEnabled(True)
        self.devices_table.setUpdatesEnabled(True)
        self.devices_table.setSortingEnabled(True)

        # Re-apply any active search/filter after table rebuild
        if hasattr(self, 'account_search_input') or hasattr(self, 'account_category_filter'):
            self.filter_main_account_tab()


    def on_device_selected(self):
        """Handle device selection - highlight corresponding account"""
        selected_rows = self.devices_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        # Get assigned UID from device row
        row = selected_rows[0].row()
        uid_item = self.devices_table.item(row, 5)  # Assigned UID column (col 5)
        if not uid_item or uid_item.text() == "—":
            return
        
        selected_uid = uid_item.text()
        
        # Find and select corresponding account in accounts table
        self.account_table.blockSignals(True)
        for account_row in range(self.account_table.rowCount()):
            account_uid_item = self.account_table.item(account_row, 1)  # UID col 1 (col 0 is #)
            if account_uid_item and account_uid_item.text() == selected_uid:
                self.account_table.selectRow(account_row)
                break
        self.account_table.blockSignals(False)
    

    def on_account_selected(self):
        """Handle account selection - highlight corresponding device"""
        selected_rows = self.account_table.selectedItems()
        if not selected_rows:
            return
        
        # Get selected UID from col 1 (UID column, col 0 is #)
        row = selected_rows[0].row()
        uid_item = self.account_table.item(row, 1)
        if not uid_item:
            return
        
        selected_uid = uid_item.text()
        
        # Find and select corresponding device in devices table
        self.devices_table.blockSignals(True)
        for device_row in range(self.devices_table.rowCount()):
            assigned_uid_item = self.devices_table.item(device_row, 5)  # Assigned UID col 5
            if assigned_uid_item and assigned_uid_item.text() == selected_uid:
                self.devices_table.selectRow(device_row)
                break
        self.devices_table.blockSignals(False)
    

    def show_device_context_menu(self, position):
        """Context menu for devices table - full device operations"""
        try:
            self._show_device_context_menu_impl(position)
        except Exception as e:
            self.add_activity(f"Context menu error: {e}")
            import traceback; traceback.print_exc()


    def _show_device_context_menu_impl(self, position):
        _MENU_STYLE = """
            QMenu { background-color: #252526; color: #cccccc; border: 1px solid #3d3d3d;
                border-radius: 6px; padding: 4px; font-size: 12px; }
            QMenu::item { padding: 8px 20px 8px 12px; border-radius: 4px; margin: 1px 2px; }
            QMenu::item:selected { background-color: rgba(33,150,243,0.2); color: #ffffff; }
            QMenu::item:disabled { color: #555555; }
            QMenu::separator { height: 1px; background-color: #3d3d3d; margin: 4px 8px; }
            QMenu QMenu { background-color: #252526; border: 1px solid #3d3d3d; border-radius: 6px; padding: 4px; }
            QMenu::right-arrow { width: 16px; height: 16px; margin-right: 4px; }
        """
        menu = QMenu()
        menu.setStyleSheet(_MENU_STYLE)

        # ── Select All + Load Devices (always visible) ────────────────────
        select_all_action = menu.addAction(qta.icon('fa5s.check-double', color='#4CAF50'), "Select All")
        load_devices_action = menu.addAction(qta.icon('fa5s.sync-alt', color='#4CAF50'), "Load Devices")
        menu.addSeparator()

        # ── Apps ──────────────────────────────────────────────────────────
        logo_dir = os.path.join(_PROJECT_ROOT, "logo")
        def _icon(path, fallback):
            p = os.path.join(logo_dir, path)
            if os.path.exists(p):
                px = QPixmap(p).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                return QIcon(px)
            return fallback
        fb_icon = _icon("Facebook_Logo.png", qta.icon('fa5b.facebook', color='#4267B2'))
        fb_lite_icon = _icon("Facebook_Lite.png", qta.icon('fa5b.facebook', color='#4267B2'))
        openvpn_icon = _icon("openvpn.png", qta.icon('fa5s.shield-alt', color='#FF9800'))

        install_menu = menu.addMenu(qta.icon('fa5s.download', color='#4CAF50'), "Install App =>")
        install_fb_action = install_menu.addAction(fb_icon, "Facebook")
        install_fb_lite_action = install_menu.addAction(fb_lite_icon, "Facebook Lite")

        uninstall_menu = menu.addMenu(fb_icon, "Uninstall App =>")
        uninstall_fb_action = uninstall_menu.addAction(fb_icon, "Facebook")
        uninstall_fb_lite_action = uninstall_menu.addAction(fb_lite_icon, "Facebook Lite")
        menu.addSeparator()

        # ── Device ────────────────────────────────────────────────────────
        view_screen_action = menu.addAction(qta.icon('fa5s.desktop', color='#4CAF50'), "View Screen")
        diagnose_screen_action = menu.addAction(qta.icon('fa5s.stethoscope', color='#FF9800'), "Diagnose Screen Casting")

        device_menu = menu.addMenu(qta.icon('fa5s.mobile-alt', color='#4CAF50'), "Device")
        set_dev_fb_action = device_menu.addAction(qta.icon('fa5s.cog', color='#4CAF50'), "Set Devices working")
        set_wallpaper_action = device_menu.addAction(qta.icon('fa5s.image', color='#2196F3'), "Set Wallpaper")
        home_screen_action = device_menu.addAction(qta.icon('fa5s.home', color='#888888'), "Home Screen")
        clear_recents_action = device_menu.addAction(qta.icon('fa5s.broom', color='#FF5722'), "Clear Recents")
        test_change_action = device_menu.addAction(qta.icon('fa5s.magic', color='#FF9800'), "Test Change info")
        switch_kb_menu = device_menu.addMenu(qta.icon('fa5s.keyboard', color='#4CAF50'), "Switch Keyboard")
        switch_kb_gboard_action = switch_kb_menu.addAction("GBoard")
        switch_kb_adb_action = switch_kb_menu.addAction("ADB Keyboard")
        menu.addSeparator()

        # ── Device Changer ────────────────────────────────────────────────
        changer_menu = menu.addMenu(qta.icon('fa5s.random', color='#FF9800'), "Device Changer")
        mc_random_action = changer_menu.addAction(qta.icon('fa5s.random', color='#FF9800'), "Change Random")
        mc_samsung_action = changer_menu.addAction(qta.icon('fa5b.android', color='#888888'), "Change Samsung")
        mc_oneplus_action = changer_menu.addAction(qta.icon('fa5b.android', color='#888888'), "Change OnePlus")
        mc_xiaomi_action = changer_menu.addAction(qta.icon('fa5b.android', color='#888888'), "Change Xiaomi")
        mc_google_action = changer_menu.addAction(qta.icon('fa5b.android', color='#888888'), "Change Google")
        changer_menu.addSeparator()
        mc_check_action = changer_menu.addAction(qta.icon('fa5s.info-circle', color='#2196F3'), "Check Current Device")
        menu.addSeparator()

        # ── VPN & Proxy ───────────────────────────────────────────────────
        vpn_menu = menu.addMenu(openvpn_icon, "VPN & Proxy")
        setup_vpn_action = vpn_menu.addAction(qta.icon('fa5s.cog', color='#FF9800'), "Setup VPN Config")
        open_vpn_action = vpn_menu.addAction(qta.icon('fa5s.shield-alt', color='#FF9800'), "Open VPN App")
        vpn_menu.addSeparator()
        connect_random_proxy_action = vpn_menu.addAction(qta.icon('fa5s.random', color='#4CAF50'), "Connect Random Proxy")
        connect_specific_proxy_action = vpn_menu.addAction(qta.icon('fa5s.map-marker-alt', color='#2196F3'), "Connect Specific Proxy")
        disconnect_proxy_action = vpn_menu.addAction(qta.icon('fa5s.times-circle', color='#f44336'), "Disconnect Proxy")
        check_proxy_action = vpn_menu.addAction(qta.icon('fa5s.info-circle', color='#888888'), "Check Proxy Status")
        menu.addSeparator()

        # ── Location & IP ─────────────────────────────────────────────────
        location_menu = menu.addMenu(qta.icon('fa5s.map-marker-alt', color='#2196F3'), "Location & IP")
        check_location_action = location_menu.addAction(qta.icon('fa5s.map-marker-alt', color='#2196F3'), "Check Location")
        set_location_action = location_menu.addAction(qta.icon('fa5s.map-pin', color='#E91E63'), "Set Location")
        check_ip_action = location_menu.addAction(qta.icon('fa5s.network-wired', color='#E91E63'), "Check IP")
        menu.addSeparator()

        # ── Apps Data ─────────────────────────────────────────────────────
        clear_fb_lite_action = menu.addAction(qta.icon('fa5s.broom', color='#FF5722'), "Clear Data FB Lite")
        clear_fb_action = menu.addAction(qta.icon('fa5s.broom', color='#FF5722'), "Clear Data Facebook")

        # ── Other ─────────────────────────────────────────────────────────
        phone_menu = menu.addMenu(qta.icon('fa5s.phone', color='#4CAF50'), "Phone")
        phone_call_action = phone_menu.addAction("Make Call")
        phone_sms_action = phone_menu.addAction("Send SMS")

        open_vpn_app_menu = menu.addMenu(openvpn_icon, "Open App VPN")
        open_openvpn_action = open_vpn_app_menu.addAction("OpenVPN")
        open_surfshark_action = open_vpn_app_menu.addAction("Surfshark")

        # Execute with menu centered on cursor position
        global_pos = self.devices_table.viewport().mapToGlobal(position)
        menu_size = menu.sizeHint()
        centered_pos = QPoint(global_pos.x() - menu_size.width() // 2, global_pos.y() - menu_size.height() // 2)
        action = menu.exec(centered_pos)
        if not action:
            return

        # Get all selected device IDs
        rows = self.devices_table.selectionModel().selectedRows()
        device_ids = [self.devices_table.item(r.row(), 1).text() for r in rows if self.devices_table.item(r.row(), 1)]
        if not device_ids and action not in (select_all_action, load_devices_action):
            return
        device_id = device_ids[0] if device_ids else None

        if action == select_all_action:
            self.devices_table.selectAll()
        elif action == load_devices_action:
            self.auto_load_devices_to_account_tab()
        elif action == install_fb_action:
            for d in device_ids: self._install_facebook_app(d, "katana")
        elif action == install_fb_lite_action:
            for d in device_ids: self._install_facebook_app(d, "lite")
        elif action == uninstall_fb_action:
            for d in device_ids: self._uninstall_facebook_app(d, "com.facebook.katana")
        elif action == uninstall_fb_lite_action:
            for d in device_ids: self._uninstall_facebook_app(d, "com.facebook.lite")
        elif action == view_screen_action:
            # Arrange windows in a grid layout
            import ctypes
            import time as time_mod
            
            # Phone window dimensions (smaller size)
            phone_width = 300   # Width of each phone window
            phone_height = 650  # Approximate height for typical phone aspect ratio
            gap = 10  # Gap between windows
            
            # Get screen dimensions
            user32 = ctypes.windll.user32
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            
            # Calculate how many phones fit per row
            phones_per_row = max(1, screen_width // (phone_width + gap))
            
            # Calculate grid layout
            num_devices = len(device_ids)
            cols = min(phones_per_row, num_devices)
            rows = (num_devices + cols - 1) // cols  # Ceiling division
            
            # Start from top-left corner with margin for title bar
            start_x = 10
            start_y = 40  # Leave space for window title bar
            
            # Launch screens with positioning
            for idx, d in enumerate(device_ids):
                row = idx // cols
                col = idx % cols
                x = start_x + col * (phone_width + gap)
                y = start_y + row * (phone_height + gap)
                
                # Launch with position and smaller size
                self._view_screen_with_position(d, x, y, max_size=600)
                time_mod.sleep(0.5)  # Small delay between launches
        elif action == diagnose_screen_action:
            if device_id: self._diagnose_screen_casting(device_id)
        elif action == setup_vpn_action:
            self._setup_vpn_single(device_id)
        elif action == open_vpn_action:
            self._temp_single_device = list(device_ids)
            self._open_vpn_app()
        elif action == connect_random_proxy_action:
            self._temp_single_device = list(device_ids)
            self._connect_random_proxy()
        elif action == connect_specific_proxy_action:
            self._temp_single_device = list(device_ids)
            self._connect_specific_proxy()
        elif action == disconnect_proxy_action:
            self._temp_single_device = list(device_ids)
            self._disconnect_proxy()
        elif action == check_proxy_action:
            for d in device_ids: self._check_proxy_status_single(d)
        elif action == test_change_action:
            self._maxchange_multi(device_ids, brand=None)
        elif action == mc_random_action:
            self._maxchange_multi(device_ids, brand=None)
        elif action == mc_samsung_action:
            self._maxchange_multi(device_ids, brand="Samsung")
        elif action == mc_oneplus_action:
            self._maxchange_multi(device_ids, brand="OnePlus")
        elif action == mc_xiaomi_action:
            self._maxchange_multi(device_ids, brand="Xiaomi")
        elif action == mc_google_action:
            self._maxchange_multi(device_ids, brand="Google")
        elif action == mc_check_action:
            for d in device_ids: self._check_maxchange_single(d)
        elif action == setup_vpn_action:
            for d in device_ids: self._open_vpn_single(d)
        elif action == switch_kb_gboard_action:
            for d in device_ids: self._switch_keyboard_single(d)
        elif action == switch_kb_adb_action:
            for d in device_ids: self._switch_keyboard_single(d)
        elif action == set_wallpaper_action:
            # Show dialog for wallpaper number selection
            if len(device_ids) == 1:
                self._set_wallpaper_single(device_id, device_ids)
            else:
                self._set_wallpaper_multiple(device_ids)
        elif action == test_change_action:
            self._maxchange_multi(device_ids, brand=None)
        elif action == check_location_action:
            self._check_location_single(device_id)
        elif action == set_location_action:
            self._set_location_single(device_id)
        elif action == check_ip_action:
            self._check_ip_single(device_id)
        elif action == open_openvpn_action:
            for d in device_ids: self._open_vpn_single(d)
        elif action == open_surfshark_action:
            for d in device_ids:
                self.add_activity(f"Opening Surfshark on {d}...")
        elif action == home_screen_action:
            for d in device_ids: self._home_screen_single(d)
        elif action == clear_recents_action:
            for d in device_ids: self._clear_recents_single(d)
            for d in device_ids: self._home_screen_single(d)
        elif action == clear_fb_lite_action:
            for d in device_ids: self._clear_facebook_data(d, "com.facebook.lite")
        elif action == clear_fb_action:
            for d in device_ids: self._clear_facebook_data(d, "com.facebook.katana")

    # ═══════════════════════════════════════════════════════════════════════
    # Single Device Operation Wrappers (for context menu)
    # ═══════════════════════════════════════════════════════════════════════


    def _install_facebook_app(self, device_id, app_type):
        """Install Facebook app on a single device"""
        import threading
        def _run():
            try:
                if app_type == "katana":
                    apk_path = "com.facebook.katana_552.1.0.45.68-469416370_minAPI28(arm64-v8a)(360,400,420,480,560,640dpi)_apkmirror.com.apk"
                    app_name = "Facebook"
                else:
                    apk_path = "com.facebook.lite_494.0.0.9.107-512801323_minAPI21(armeabi-v7a)(nodpi)_apkmirror.com.apk"
                    app_name = "Facebook Lite"

                if not os.path.exists(apk_path):
                    self.add_activity(f"✗ APK not found: {apk_path}")
                    QMetaObject.invokeMethod(self, "_show_fb_install_dialog",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, app_name), Q_ARG(str, device_id), Q_ARG(bool, False), Q_ARG(str, "APK file not found"))
                    return

                self.add_activity(f"Installing {app_name} on {device_id}...")
                result = safe_subprocess_run([self.adb_path, "-s", device_id, "install", "-r", apk_path],
                                            capture_output=True, text=True, timeout=120)
                if "Success" in result.stdout:
                    self.add_activity(f"✓ {app_name} installed on {device_id}")
                    QMetaObject.invokeMethod(self, "_show_fb_install_dialog",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, app_name), Q_ARG(str, device_id), Q_ARG(bool, True), Q_ARG(str, ""))
                else:
                    err = result.stderr.strip() if result.stderr else "Unknown error"
                    self.add_activity(f"✗ Failed to install {app_name} on {device_id}")
                    QMetaObject.invokeMethod(self, "_show_fb_install_dialog",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, app_name), Q_ARG(str, device_id), Q_ARG(bool, False), Q_ARG(str, err))
            except Exception as e:
                self.add_activity(f"✗ Error installing on {device_id}: {str(e)}")
                QMetaObject.invokeMethod(self, "_show_fb_install_dialog",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, app_type), Q_ARG(str, device_id), Q_ARG(bool, False), Q_ARG(str, str(e)))
        threading.Thread(target=_run, daemon=True).start()

    @pyqtSlot(str, str, bool, str)

    def _show_fb_install_dialog(self, app_name, device_id, success, error_msg):
        """Show finish dialog for Facebook install on main thread"""
        if success:
            QMessageBox.information(self, "Install Complete",
                f"✅ {app_name} installed successfully\n\nDevice: {device_id}")
        else:
            QMessageBox.warning(self, "Install Failed",
                f"❌ Failed to install {app_name}\n\nDevice: {device_id}\n\n{error_msg}")


    def _uninstall_facebook_app(self, device_id, package):
        """Uninstall Facebook app from a single device"""
        import threading
        def _run():
            try:
                app_name = "Facebook" if "katana" in package else "Facebook Lite"
                self.add_activity(f"Uninstalling {app_name} from {device_id}...")
                result = safe_subprocess_run([self.adb_path, "-s", device_id, "uninstall", package],
                                            capture_output=True, text=True, timeout=60)
                if "Success" in result.stdout:
                    self.add_activity(f"✓ {app_name} uninstalled from {device_id}")
                    QMetaObject.invokeMethod(self, "_show_fb_uninstall_dialog",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, app_name), Q_ARG(str, device_id), Q_ARG(bool, True), Q_ARG(str, ""))
                else:
                    err = result.stderr.strip() if result.stderr else "Unknown error"
                    self.add_activity(f"✗ Failed to uninstall {app_name} from {device_id}")
                    QMetaObject.invokeMethod(self, "_show_fb_uninstall_dialog",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, app_name), Q_ARG(str, device_id), Q_ARG(bool, False), Q_ARG(str, err))
            except Exception as e:
                self.add_activity(f"✗ Error uninstalling from {device_id}: {str(e)}")
                QMetaObject.invokeMethod(self, "_show_fb_uninstall_dialog",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, package), Q_ARG(str, device_id), Q_ARG(bool, False), Q_ARG(str, str(e)))
        threading.Thread(target=_run, daemon=True).start()

    @pyqtSlot(str, str, bool, str)

    def _show_fb_uninstall_dialog(self, app_name, device_id, success, error_msg):
        """Show finish dialog for Facebook uninstall on main thread"""
        if success:
            QMessageBox.information(self, "Uninstall Complete",
                f"✅ {app_name} uninstalled successfully\n\nDevice: {device_id}")
        else:
            QMessageBox.warning(self, "Uninstall Failed",
                f"❌ Failed to uninstall {app_name}\n\nDevice: {device_id}\n\n{error_msg}")


    def _clear_facebook_data(self, device_id, package):
        """Clear Facebook app data on a single device"""
        import threading
        def _run():
            try:
                app_name = "Facebook" if "katana" in package else "Facebook Lite"
                self.add_activity(f"Clearing {app_name} data on {device_id}...")
                result = safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "pm", "clear", package],
                                            capture_output=True, text=True, timeout=30)
                if "Success" in result.stdout:
                    self.add_activity(f"✓ {app_name} data cleared on {device_id}")
                else:
                    self.add_activity(f"✗ Failed to clear {app_name} data on {device_id}")
            except Exception as e:
                self.add_activity(f"✗ Error clearing data on {device_id}: {str(e)}")
        threading.Thread(target=_run, daemon=True).start()


    def _diagnose_screen_casting(self, device_id):
        """Deep diagnostic check for screen casting issues"""
        import subprocess, time
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Screen Casting Diagnostics - {device_id}")
        dialog.setMinimumSize(700, 500)
        layout = QVBoxLayout(dialog)
        
        # Title
        title = QLabel(f"🔍 Deep Diagnostic Check for Device: {device_id}")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # Results text area
        results = QTextEdit()
        results.setReadOnly(True)
        results.setStyleSheet("background: #1e1e1e; color: #d4d4d4; font-family: Consolas; padding: 10px;")
        layout.addWidget(results)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.show()
        QApplication.processEvents()
        
        def log(msg, color="#d4d4d4"):
            results.append(f'<span style="color: {color};">{msg}</span>')
            QApplication.processEvents()
        
        def run_check(title, cmd, timeout=10):
            log(f"\n{'='*60}", "#888888")
            log(f"🔍 {title}", "#4CAF50")
            log(f"{'='*60}", "#888888")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
                if result.returncode == 0:
                    output = result.stdout.strip()
                    log(f"✓ Success", "#4CAF50")
                    if output:
                        log(f"{output}", "#d4d4d4")
                    return True, output
                else:
                    log(f"✗ Failed (exit code: {result.returncode})", "#f44336")
                    if result.stderr:
                        log(f"Error: {result.stderr.strip()}", "#FF9800")
                    return False, result.stderr
            except subprocess.TimeoutExpired:
                log(f"⏱ Timeout after {timeout}s", "#FF9800")
                return False, "Timeout"
            except Exception as e:
                log(f"✗ Exception: {str(e)}", "#f44336")
                return False, str(e)
        
        # Start diagnostics
        log("Starting comprehensive screen casting diagnostics...\n", "#2196F3")
        time.sleep(0.5)
        
        # 1. Check if device is connected
        success, output = run_check(
            "Check Device Connection",
            f'"{self.adb_path}" devices'
        )
        if device_id not in output:
            log(f"\n❌ CRITICAL: Device {device_id} is NOT connected!", "#f44336")
            log("Solution: Reconnect USB cable and check 'adb devices'", "#FF9800")
            return
        else:
            log(f"✓ Device {device_id} is connected", "#4CAF50")
        
        # 2. Check device state
        run_check(
            "Check Device State",
            f'"{self.adb_path}" -s {device_id} get-state'
        )
        
        # 3. Check USB debugging authorization
        success, output = run_check(
            "Check USB Debugging Authorization",
            f'"{self.adb_path}" -s {device_id} shell "getprop ro.debuggable"'
        )
        
        # 4. Check device properties
        run_check(
            "Device Model & Android Version",
            f'"{self.adb_path}" -s {device_id} shell "getprop ro.product.model && getprop ro.build.version.release"'
        )
        
        # 5. Check screen state
        success, output = run_check(
            "Check Screen State",
            f'"{self.adb_path}" -s {device_id} shell "dumpsys power | grep mScreenOn"'
        )
        if "false" in output.lower():
            log("⚠ Screen is OFF - this may prevent casting", "#FF9800")
        
        # 6. Check if scrcpy server can be pushed
        log(f"\n{'='*60}", "#888888")
        log("🔍 Test scrcpy Server Push", "#4CAF50")
        log(f"{'='*60}", "#888888")
        try:
            test_file = os.path.join(_PROJECT_ROOT, "scrcpy-win64-v3.1", "scrcpy-server")
            if not os.path.exists(test_file):
                log(f"⚠ scrcpy-server file not found at: {test_file}", "#FF9800")
            else:
                result = subprocess.run(
                    [self.adb_path, "-s", device_id, "push", test_file, "/data/local/tmp/scrcpy-server-test.jar"],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    log("✓ Successfully pushed test file to device", "#4CAF50")
                    # Clean up
                    subprocess.run([self.adb_path, "-s", device_id, "shell", "rm", "/data/local/tmp/scrcpy-server-test.jar"],
                                 capture_output=True, timeout=5)
                else:
                    log(f"✗ Failed to push file: {result.stderr}", "#f44336")
                    log("This indicates storage permission or space issues", "#FF9800")
        except Exception as e:
            log(f"✗ Push test failed: {str(e)}", "#f44336")
        
        # 7. Check available storage
        run_check(
            "Check /data/local/tmp Storage",
            f'"{self.adb_path}" -s {device_id} shell "df /data/local/tmp"'
        )
        
        # 8. Check for existing scrcpy processes
        run_check(
            "Check for Running scrcpy Processes",
            f'"{self.adb_path}" -s {device_id} shell "ps | grep scrcpy"'
        )
        
        # 9. Test socket connection
        log(f"\n{'='*60}", "#888888")
        log("🔍 Test ADB Socket Connection", "#4CAF50")
        log(f"{'='*60}", "#888888")
        success, output = run_check(
            "Test Shell Command Response Time",
            f'"{self.adb_path}" -s {device_id} shell "echo test"',
            timeout=5
        )
        
        # 10. Check USB connection speed
        run_check(
            "Check USB Connection Info",
            f'"{self.adb_path}" -s {device_id} shell "getprop sys.usb.state"'
        )
        
        # 11. Try to get display info
        run_check(
            "Get Display Information",
            f'"{self.adb_path}" -s {device_id} shell "dumpsys display | grep mBaseDisplayInfo"'
        )
        
        # 12. Check for SELinux restrictions
        run_check(
            "Check SELinux Status",
            f'"{self.adb_path}" -s {device_id} shell "getenforce"'
        )
        
        # 13. Test actual scrcpy connection
        log(f"\n{'='*60}", "#888888")
        log("🔍 Test Actual scrcpy Connection", "#4CAF50")
        log(f"{'='*60}", "#888888")
        
        scrcpy_path = os.path.join(_PROJECT_ROOT, "scrcpy-win64-v3.1", "scrcpy.exe")
        if os.path.exists(scrcpy_path):
            log("Attempting to start scrcpy (will timeout after 5 seconds)...", "#2196F3")
            try:
                import os as _os
                env = _os.environ.copy()
                env["ADB"] = self.adb_path
                
                process = subprocess.Popen(
                    [scrcpy_path, "-s", device_id, "--no-window", "--no-audio"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                time.sleep(3)
                
                if process.poll() is None:
                    log("✓ scrcpy process started successfully!", "#4CAF50")
                    log("The device CAN cast - killing test process...", "#4CAF50")
                    process.terminate()
                    time.sleep(0.5)
                    process.kill()
                else:
                    stdout, stderr = process.communicate(timeout=2)
                    error_msg = stderr.decode('utf-8', errors='ignore')
                    log("✗ scrcpy failed to start", "#f44336")
                    log(f"Error output:\n{error_msg}", "#FF9800")
                    
                    # Analyze error
                    if "could not find any ADB device" in error_msg:
                        log("\n❌ ROOT CAUSE: ADB cannot see the device", "#f44336")
                        log("Solution: Restart ADB server or reconnect device", "#FF9800")
                    elif "device unauthorized" in error_msg:
                        log("\n❌ ROOT CAUSE: Device not authorized for USB debugging", "#f44336")
                        log("Solution: Check device screen for authorization prompt", "#FF9800")
                    elif "closed" in error_msg or "connection" in error_msg.lower():
                        log("\n❌ ROOT CAUSE: Connection closed/unstable", "#f44336")
                        log("Solution: Try different USB cable or port", "#FF9800")
                    elif "server" in error_msg.lower():
                        log("\n❌ ROOT CAUSE: scrcpy server failed to start on device", "#f44336")
                        log("Solution: Check device permissions and storage", "#FF9800")
                        
            except Exception as e:
                log(f"✗ Test failed with exception: {str(e)}", "#f44336")
        else:
            log(f"✗ scrcpy.exe not found at: {scrcpy_path}", "#f44336")
        
        # Summary
        log(f"\n{'='*60}", "#888888")
        log("📋 DIAGNOSTIC SUMMARY", "#2196F3")
        log(f"{'='*60}", "#888888")
        log(f"Device ID: {device_id}", "#d4d4d4")
        log("\nCommon solutions to try:", "#FFD700")
        log("1. Reconnect USB cable (try different port)", "#d4d4d4")
        log("2. Revoke and re-authorize USB debugging on device", "#d4d4d4")
        log("3. Restart ADB: adb kill-server && adb start-server", "#d4d4d4")
        log("4. Wake up device screen", "#d4d4d4")
        log("5. Check if device has enough storage space", "#d4d4d4")
        log("6. Try a different USB cable (data cable, not charge-only)", "#d4d4d4")
        log("\n✓ Diagnostics complete!", "#4CAF50")


    def _view_screen_single(self, device_id):
        """Open scrcpy for a single device — keeps it alive with auto-restart."""
        self._view_screen_with_position(device_id, None, None, max_size=600)
    
    
    def _view_screen_with_position(self, device_id, x=None, y=None, max_size=None):
        """Open scrcpy for a single device with optional window positioning and size."""
        import subprocess, shutil, zipfile, time, threading
        base = _PROJECT_ROOT

        # Auto-extract zip if needed
        zip_path = os.path.join(base, "scrcpy.zip")
        scrcpy_exe = os.path.join(base, "scrcpy-win64-v3.1", "scrcpy.exe")
        if os.path.exists(zip_path) and not os.path.exists(scrcpy_exe):
            try:
                with zipfile.ZipFile(zip_path, 'r') as z:
                    for member in z.namelist():
                        if 'adb' in member.lower():
                            continue
                        target = os.path.join(base, member)
                        if not os.path.exists(target):
                            try:
                                z.extract(member, base)
                            except Exception:
                                pass
                self.add_activity("Extracted scrcpy")
            except Exception as e:
                self.add_activity(f"Extract warning: {e}")

        # Search for scrcpy.exe AFTER extraction
        search_paths = [
            os.path.join(base, "scrcpy-win64-v3.1", "scrcpy.exe"),
            os.path.join(base, "scrcpy-win64-v3.1", "scrcpy-win64-v3.1", "scrcpy.exe"),
            os.path.join(base, "scrcpy.exe"),
        ]
        scrcpy_path = next((p for p in search_paths if os.path.exists(p)), None)
        if not scrcpy_path:
            scrcpy_path = shutil.which("scrcpy")

        if not scrcpy_path:
            QMessageBox.warning(self, "scrcpy Not Found",
                "scrcpy.exe not found.\n\nPlease extract scrcpy-win64-v3.1.zip into the application folder.")
            return

        # Verify device is connected
        try:
            r = subprocess.run([self.adb_path, "devices"], capture_output=True, text=True, timeout=5)
            if device_id not in r.stdout:
                self.add_activity(f"✗ Device {device_id} not connected")
                return
        except Exception as e:
            self.add_activity(f"✗ Failed to check device connection: {str(e)}")
            return

        # Store processes dict on self so they stay alive
        if not hasattr(self, '_scrcpy_procs'):
            self._scrcpy_procs = {}

        # If already running for this device, do nothing
        existing = self._scrcpy_procs.get(device_id)
        if existing and existing.poll() is None:
            self.add_activity(f"ℹ Screen view already open for {device_id}")
            return

        import os as _os
        env = _os.environ.copy()
        env["ADB"] = self.adb_path

        def _launch():
            try:
                # Build basic scrcpy command
                cmd = [scrcpy_path, "-s", device_id]
                
                # Add window positioning if coordinates provided
                if x is not None and y is not None:
                    cmd.extend(["--window-x", str(x), "--window-y", str(y)])
                    # Try using window-width and window-height for grid layout
                    if max_size:
                        cmd.extend(["--window-width", str(int(max_size * 0.5)), "--window-height", str(max_size)])
                elif max_size:
                    # Use max-size only when not positioning
                    cmd.extend(["--max-size", str(max_size)])
                
                cmd.extend(["--window-title", f"FRT - {device_id}"])
                
                proc = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._scrcpy_procs[device_id] = proc
                
                # Wait and check if it started successfully
                time.sleep(1.5)
                if proc.poll() is not None:
                    self.add_activity(f"✗ {device_id}: scrcpy failed to start (exit code: {proc.returncode})")
                    return
                    
                self.add_activity(f"✓ Opened screen view for {device_id}")

                # Watcher — auto-restart if scrcpy closes unexpectedly
                while True:
                    proc.wait()  # block until process exits
                    # Check if this device is still in our dict (not manually closed)
                    if self._scrcpy_procs.get(device_id) is not proc:
                        break  # was replaced or removed — stop watching
                    # Check device still connected and ready before restarting
                    try:
                        r2 = subprocess.run([self.adb_path, "devices"],
                            capture_output=True, text=True, timeout=5)
                        stdout = r2.stdout or ""
                        # Check device is present AND in 'device' state (not offline/unauthorized)
                        device_ready = any(
                            line.startswith(device_id) and "device" in line.split("\t")[-1]
                            for line in stdout.splitlines()
                            if "\t" in line
                        )
                        if not device_ready:
                            # Retry up to 5 times with 2s gap — VPN/network changes
                            # can cause a transient ADB offline state for several seconds
                            for _retry in range(5):
                                time.sleep(2)
                                r3 = subprocess.run([self.adb_path, "devices"],
                                    capture_output=True, text=True, timeout=5)
                                stdout3 = r3.stdout or ""
                                device_ready = any(
                                    line.startswith(device_id) and "device" in line.split("\t")[-1]
                                    for line in stdout3.splitlines()
                                    if "\t" in line
                                )
                                if device_ready:
                                    break  # came back online — restart scrcpy normally
                        # If device is in the middle of a VPN operation, never kill the screen
                        _vpn_busy = getattr(self, '_vpn_busy_devices', set())
                        if not device_ready and device_id in _vpn_busy:
                            self.add_activity(f"↺ {device_id}: ADB offline during VPN op — waiting...")
                            time.sleep(3)
                            continue  # loop back and wait for proc.wait() again
                        if not device_ready:
                            self.add_activity(f"ℹ {device_id}: Device disconnected — screen view closed")
                            self._scrcpy_procs.pop(device_id, None)
                            break
                    except Exception as e:
                        self.add_activity(f"⚠ {device_id}: ADB check failed ({e}) — stopping screen view")
                        self._scrcpy_procs.pop(device_id, None)
                        break
                    self.add_activity(f"↺ {device_id}: Screen view closed — restarting...")
                    # Check if auto-restart is enabled
                    from src.core.config import load_config as _load_cfg
                    if not _load_cfg().get('auto_restart_screen', True):
                        self.add_activity(f"ℹ {device_id}: Auto restart disabled — screen view stopped")
                        self._scrcpy_procs.pop(device_id, None)
                        break
                    time.sleep(2)
                    proc = subprocess.Popen(
                        cmd,
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self._scrcpy_procs[device_id] = proc
                    time.sleep(0.8)
                    if proc.poll() is not None:
                        self.add_activity(f"✗ {device_id}: Screen view failed to restart")
                        self._scrcpy_procs.pop(device_id, None)
                        break
                    self.add_activity(f"✓ {device_id}: Screen view restarted")

            except Exception as e:
                self.add_activity(f"✗ Failed to open screen: {str(e)}")

        threading.Thread(target=_launch, daemon=True).start()


    def _set_devices_working_single(self, device_id):
        """Configure device settings for a single device"""
        self.add_activity(f"Configuring device settings for {device_id}...")
        QMessageBox.information(self, "Device Settings", f"Device settings configuration for {device_id}")


    def _switch_keyboard_single(self, device_id):
        """Switch keyboard for a single device"""
        try:
            result = safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "ime", "list", "-s"],
                                        capture_output=True, text=True, timeout=10)
            imes = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            if len(imes) < 2:
                QMessageBox.warning(self, "Keyboard", "Only one keyboard installed on device")
                return
            current_ime = safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "settings", "get", "secure", "default_input_method"],
                                             capture_output=True, text=True, timeout=10).stdout.strip()
            next_ime = imes[1] if current_ime == imes[0] else imes[0]
            safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "ime", "set", next_ime],
                               capture_output=True, text=True, timeout=10)
            self.add_activity(f"✓ Switched keyboard on {device_id}")
        except Exception as e:
            self.add_activity(f"✗ Failed to switch keyboard: {str(e)}")


    def _set_wallpaper_single(self, device_id, device_ids=None):
        """Set wallpaper for a single device - shows dialog to choose wallpaper number"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QSpinBox, QPushButton, QHBoxLayout
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Set Wallpaper")
        dialog.setModal(True)
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout()
        
        # Label
        label = QLabel(f"Choose wallpaper number for device:\n{device_id}")
        label.setStyleSheet("color: #d4d4d4; font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(label)
        
        # Number input
        number_layout = QHBoxLayout()
        number_label = QLabel("Wallpaper Number:")
        number_label.setStyleSheet("color: #d4d4d4;")
        number_layout.addWidget(number_label)
        
        number_input = QSpinBox()
        number_input.setMinimum(1)
        number_input.setMaximum(999)
        number_input.setValue(1)
        number_input.setStyleSheet("""
            QSpinBox {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                font-size: 14px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #3d3d3d;
                border: 1px solid #555;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #4d4d4d;
            }
        """)
        number_layout.addWidget(number_input)
        layout.addLayout(number_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("Set Wallpaper")
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        ok_button.clicked.connect(dialog.accept)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.setStyleSheet("QDialog { background-color: #1e1e1e; }")
        
        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            wallpaper_number = number_input.value()
            # Use provided device_ids or fallback to single device
            self._temp_devices_for_wallpaper = device_ids if device_ids else [device_id]
            self._temp_wallpaper_number = wallpaper_number
            self._set_wallpaper_with_order()


    def _set_wallpaper_multiple(self, device_ids):
        """Set wallpaper for multiple devices - shows dialog to choose number range"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QSpinBox, QPushButton, QHBoxLayout, QRadioButton, QButtonGroup
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Set Wallpaper")
        dialog.setModal(True)
        dialog.setMinimumWidth(380)
        
        layout = QVBoxLayout()
        
        # Label
        label = QLabel(f"Setting wallpaper for {len(device_ids)} devices")
        label.setStyleSheet("color: #d4d4d4; font-size: 13px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(label)
        
        # Radio buttons for mode selection
        mode_group = QButtonGroup(dialog)
        
        auto_radio = QRadioButton("Auto-assign numbers (uses saved device numbers)")
        auto_radio.setStyleSheet("color: #d4d4d4; font-size: 12px;")
        auto_radio.setChecked(True)
        mode_group.addButton(auto_radio, 1)
        layout.addWidget(auto_radio)
        
        manual_radio = QRadioButton("Assign specific number range:")
        manual_radio.setStyleSheet("color: #d4d4d4; font-size: 12px; margin-top: 5px;")
        mode_group.addButton(manual_radio, 2)
        layout.addWidget(manual_radio)
        
        # Number range inputs (for manual mode)
        range_layout = QHBoxLayout()
        range_layout.addSpacing(30)  # Indent
        
        from_label = QLabel("From:")
        from_label.setStyleSheet("color: #d4d4d4; font-size: 12px;")
        range_layout.addWidget(from_label)
        
        from_input = QSpinBox()
        from_input.setMinimum(1)
        from_input.setMaximum(999)
        from_input.setValue(1)
        from_input.setEnabled(False)  # Disabled by default
        from_input.setStyleSheet("""
            QSpinBox {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                font-size: 14px;
            }
            QSpinBox:disabled {
                background-color: #1e1e1e;
                color: #666;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #3d3d3d;
                border: 1px solid #555;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #4d4d4d;
            }
        """)
        range_layout.addWidget(from_input)
        
        to_label = QLabel("To:")
        to_label.setStyleSheet("color: #d4d4d4; font-size: 12px; margin-left: 10px;")
        range_layout.addWidget(to_label)
        
        to_input = QSpinBox()
        to_input.setMinimum(1)
        to_input.setMaximum(999)
        to_input.setValue(len(device_ids))  # Default to number of devices
        to_input.setEnabled(False)  # Disabled by default
        to_input.setStyleSheet(from_input.styleSheet())
        range_layout.addWidget(to_input)
        
        range_layout.addStretch()
        layout.addLayout(range_layout)
        
        # Enable/disable inputs based on radio selection
        def on_mode_changed():
            enabled = manual_radio.isChecked()
            from_input.setEnabled(enabled)
            to_input.setEnabled(enabled)
            if enabled:
                # Auto-calculate 'to' value when switching to manual mode
                to_input.setValue(from_input.value() + len(device_ids) - 1)
        
        # Auto-update 'to' value when 'from' changes
        def on_from_changed():
            if manual_radio.isChecked():
                to_input.setValue(from_input.value() + len(device_ids) - 1)
        
        auto_radio.toggled.connect(on_mode_changed)
        manual_radio.toggled.connect(on_mode_changed)
        from_input.valueChanged.connect(on_from_changed)
        
        # Info label
        info_label = QLabel(f"Example: From 5 to 8 assigns #5, #6, #7, #8 to the {len(device_ids)} devices")
        info_label.setStyleSheet("color: #888; font-size: 10px; margin-top: 10px;")
        layout.addWidget(info_label)
        
        # Warning label for range mismatch
        warning_label = QLabel("")
        warning_label.setStyleSheet("color: #FF9800; font-size: 10px;")
        layout.addWidget(warning_label)
        
        def check_range():
            if manual_radio.isChecked():
                range_size = to_input.value() - from_input.value() + 1
                if range_size != len(device_ids):
                    warning_label.setText(f"⚠ Range size ({range_size}) doesn't match device count ({len(device_ids)})")
                else:
                    warning_label.setText("")
        
        from_input.valueChanged.connect(check_range)
        to_input.valueChanged.connect(check_range)
        manual_radio.toggled.connect(check_range)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        cancel_button.clicked.connect(dialog.reject)
        
        ok_button = QPushButton("Set Wallpapers")
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        ok_button.clicked.connect(dialog.accept)
        
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.setStyleSheet("QDialog { background-color: #1e1e1e; }")
        
        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if manual_radio.isChecked():
                # Manual range mode
                from_num = from_input.value()
                to_num = to_input.value()
                
                # Validate range
                range_size = to_num - from_num + 1
                if range_size != len(device_ids):
                    QMessageBox.warning(self, "Invalid Range", 
                        f"Range size ({range_size}) must match the number of selected devices ({len(device_ids)}).\n\n"
                        f"Please adjust the range or select different devices.")
                    return
                
                self._temp_wallpaper_range = (from_num, to_num)
            else:
                # Auto-assign mode
                self._temp_wallpaper_range = None
            
            # Store the device IDs to use
            self._temp_devices_for_wallpaper = device_ids
            self._set_wallpaper_with_order()




    def _home_screen_single(self, device_id):
        """Go to home screen on a single device"""
        try:
            safe_subprocess_run([self.adb_path, "-s", device_id, "shell", "input", "keyevent", "KEYCODE_HOME"],
                               capture_output=True, text=True, timeout=10)
            self.add_activity(f"✓ Sent home command to {device_id}")
        except Exception as e:
            self.add_activity(f"✗ Failed to go home: {str(e)}")


    def _clear_recents_single(self, device_id):
        """Clear recent apps on a single device"""
        import threading, re as _re
        def _run():
            try:
                adb = self.adb_path

                # Open recents
                subprocess.run([adb, "-s", device_id, "shell", "input", "keyevent", "KEYCODE_APP_SWITCH"],
                    capture_output=True, timeout=5)
                time.sleep(2)

                # Swipe cards up one by one (up to 15 apps)
                for _ in range(15):
                    # Dump UI to find current front card
                    subprocess.run([adb, "-s", device_id, "shell", "uiautomator", "dump", "/sdcard/ui_rc.xml"],
                        capture_output=True, timeout=8)
                    r = subprocess.run([adb, "-s", device_id, "shell", "cat", "/sdcard/ui_rc.xml"],
                        capture_output=True, text=True, timeout=5)
                    xml = r.stdout or ""

                    # Check if recents is empty
                    if 'No recent items' in xml or 'content-desc="No recent' in xml:
                        break

                    # Find the main card bounds
                    m = _re.search(r'id/snapshot.*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
                    if m:
                        x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                        cx = (x1 + x2) // 2
                        cy = (y1 + y2) // 2
                    else:
                        cx, cy = 540, 790  # fallback to known good coords

                    subprocess.run([adb, "-s", device_id, "shell", "input", "swipe",
                        str(cx), str(cy), str(cx), "50", "150"],
                        capture_output=True, timeout=3)
                    time.sleep(0.5)

                # Go home
                subprocess.run([adb, "-s", device_id, "shell", "input", "keyevent", "KEYCODE_HOME"],
                    capture_output=True, timeout=3)

                self.add_activity(f"✓ Cleared recents on {device_id}")
            except Exception as e:
                self.add_activity(f"✗ Failed to clear recents: {str(e)}")
        threading.Thread(target=_run, daemon=True).start()



    def _maxchange_multi(self, device_ids, brand=None):
        """Run maxchange on multiple devices in parallel, show one finish dialog."""
        import threading, concurrent.futures as _cf
        def _run():
            with _cf.ThreadPoolExecutor(max_workers=len(device_ids)) as ex:
                if brand:
                    futs = [ex.submit(self._maxchange_brand_single, d, brand) for d in device_ids]
                else:
                    futs = [ex.submit(self._maxchange_random_single, d) for d in device_ids]
                _cf.wait(futs)
            self._show_dialog_signal.emit("Done", f"Device change complete for {len(device_ids)} device(s).")
        threading.Thread(target=_run, daemon=True).start()


    def _maxchange_random_single(self, device_id):
        """Change device profile using MaxChange - uses the account backup assigned to this device"""
        import threading, shutil

        def _run():
            try:
                self.add_activity(f"Changing device profile for {device_id}...")

                backup_root = os.path.join(_PROJECT_ROOT, "account_backup")
                maxchanger_dir = os.path.join(_PROJECT_ROOT, "maxchanger")
                os.makedirs(maxchanger_dir, exist_ok=True)

                # Pick a random profile from account_backup for every device
                import random as _random
                profile_src = None
                if os.path.exists(backup_root):
                    candidates = []
                    for folder in os.listdir(backup_root):
                        dev_info_dir = os.path.join(backup_root, folder, "Device info")
                        if os.path.isdir(dev_info_dir):
                            for f in os.listdir(dev_info_dir):
                                if f.endswith(".tar.gz"):
                                    candidates.append(os.path.join(dev_info_dir, f))
                    if candidates:
                        profile_src = _random.choice(candidates)
                        self.add_activity(f"📂 {device_id}: Random profile: {os.path.basename(profile_src)}")

                # Copy profile into a unique temp subfolder so concurrent workers don't cross-pick profiles
                if profile_src:
                    import uuid
                    tmp_dir = os.path.join(maxchanger_dir, f"tmp_{uuid.uuid4().hex[:8]}")
                    os.makedirs(tmp_dir, exist_ok=True)
                    dest = os.path.join(tmp_dir, os.path.basename(profile_src))
                    shutil.copy2(profile_src, dest)
                else:
                    tmp_dir = maxchanger_dir
                    dest = None

                # Use _MaxChangeWorker (same as the working device changer)
                base_dir = _PROJECT_ROOT
                # Point worker at the isolated tmp_dir so it only sees this device's profile
                from src.workers.maxchange_worker import MaxChangeWorker as _MaxChangeWorker
                worker = _MaxChangeWorker([device_id], None, self.adb_path, base_dir)
                worker.maxchanger_dir = tmp_dir
                worker.progress.connect(self.add_activity)
                worker.spoof_updated.connect(self._update_spoof_in_table_ui)
                worker.start()
                worker.wait()

                # Clean up temp folder
                try:
                    import shutil as _shutil
                    if tmp_dir != maxchanger_dir and os.path.exists(tmp_dir):
                        _shutil.rmtree(tmp_dir)
                except Exception:
                    pass

            except Exception as e:
                self.add_activity(f"✗ Device change failed: {str(e)}")

        threading.Thread(target=_run, daemon=True).start()


    def _maxchange_brand_single(self, device_id, brand):
        """Change device to specific brand profile using MaxChange"""
        import threading
        def _run():
            try:
                self.add_activity(f"Changing device to {brand} profile for {device_id}...")
                result = self._apply_maxchange_professional(device_id, brand_filter=brand)
                if result:
                    self.add_activity(f"✓ {brand} profile applied: {result} on {device_id}")
                else:
                    self.add_activity(f"✗ {brand} profile failed for {device_id}")
            except Exception as e:
                self.add_activity(f"✗ Failed: {str(e)}")
        threading.Thread(target=_run, daemon=True).start()


    def _check_maxchange_single(self, device_id):
        """Check current device info via MaxChange"""
        import threading
        def _run():
            try:
                info = self._get_current_device_info(device_id)
                model = info.get('model', 'Unknown')
                manufacturer = info.get('manufacturer', 'Unknown')
                android_id = info.get('android_id', 'Unknown')
                self.add_activity(f"Device {device_id}: {manufacturer} {model} | ID: {android_id}")
            except Exception as e:
                self.add_activity(f"✗ Check failed: {str(e)}")
        threading.Thread(target=_run, daemon=True).start()


    def _setup_vpn_single(self, device_id):
        """Setup VPN on a single device"""
        self.add_activity(f"Setting up VPN for {device_id}...")


    def _open_vpn_single(self, device_id):
        """Open VPN app on a single device"""
        import threading
        def _run():
            adb = self.adb_path
            try:
                result = subprocess.run([adb, "-s", device_id, "shell",
                    "am start -n de.blinkt.openvpn/.activities.MainActivity"],
                    capture_output=True, timeout=5)
                if result.returncode == 0:
                    self.add_activity(f"✓ OpenVPN app opened on {device_id}")
                else:
                    self.add_activity(f"✗ Failed to open OpenVPN on {device_id}")
            except Exception as e:
                self.add_activity(f"✗ Error: {str(e)}")
        threading.Thread(target=_run, daemon=True).start()


    def _check_ip_single(self, device_id):
        """Check IP for a single device"""
        import threading
        def _run():
            self._temp_single_device = [device_id]
            self._check_ip()
        threading.Thread(target=_run, daemon=True).start()


    def _connect_random_proxy_single(self, device_id):
        """Connect random proxy for a single device"""
        self._temp_single_device = [device_id]
        self._connect_random_proxy()


    def _connect_specific_proxy_single(self, device_id):
        """Connect specific proxy for a single device"""
        self._temp_single_device = [device_id]
        self._connect_specific_proxy()


    def _disconnect_proxy_single(self, device_id):
        """Disconnect OpenVPN silently by force-stopping the service"""
        import threading, time
        def _do():
            adb = self.adb_path
            # Mark device as VPN-busy so the scrcpy watcher won't kill the screen
            if not hasattr(self, '_vpn_busy_devices'):
                self._vpn_busy_devices = set()
            self._vpn_busy_devices.add(device_id)
            try:
                self.add_activity(f"Disconnecting VPN on {device_id}...")
                subprocess.run([adb, "-s", device_id, "shell",
                    "am startservice -n de.blinkt.openvpn/.core.OpenVPNService --es cmd stop"],
                    capture_output=True, timeout=5)
                time.sleep(1)
                subprocess.run([adb, "-s", device_id, "shell",
                    "am broadcast -a de.blinkt.openvpn.DISCONNECT_VPN --es STOP_REASON user"],
                    capture_output=True, timeout=5)
                time.sleep(1)
                subprocess.run([adb, "-s", device_id, "shell",
                    "am force-stop de.blinkt.openvpn"],
                    capture_output=True, timeout=5)
                time.sleep(1)
                self._update_proxy_in_cache(device_id, "")
                self.add_activity(f"✓ VPN disconnected on {device_id}")
                self._show_dialog_signal.emit("Done", f"VPN disconnected on {device_id}")
            except Exception as e:
                self.add_activity(f"✗ Failed to disconnect VPN: {str(e)}")
            finally:
                # Give ADB 3 extra seconds to stabilise before allowing scrcpy watcher to act
                time.sleep(3)
                self._vpn_busy_devices.discard(device_id)
        threading.Thread(target=_do, daemon=True).start()


    def _check_proxy_status_single(self, device_id):
        """Check proxy status for a single device"""
        import threading, re
        def _do():
            adb = self.adb_path
            try:
                tun = subprocess.run([adb, "-s", device_id, "shell", "ip addr show tun0"],
                    capture_output=True, text=True, timeout=5)
                if tun.stdout and "inet" in tun.stdout:
                    m = re.search(r'inet (\S+)', tun.stdout)
                    ip = m.group(1) if m else "unknown"
                    msg = f"VPN Connected\nInterface: tun0\nIP: {ip}"
                else:
                    msg = "No VPN connected"
                QTimer.singleShot(0, lambda: QMessageBox.information(self, f"Proxy Status - {device_id}", msg))
            except Exception as e:
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "Error", str(e)))
        threading.Thread(target=_do, daemon=True).start()


    def _check_location_single(self, device_id):
        """Check location for a single device"""
        self.add_activity(f"Checking location for {device_id}...")


    def _set_location_single(self, device_id):
        """Set location for a single device"""
        self.add_activity(f"Setting location for {device_id}...")


    def _assign_account_to_device(self, uid, folder_name, parent_dialog):
        try:
            # Get list of connected devices
            result = safe_subprocess_run([self.adb_path, "devices"], 
                                        capture_output=True, text=True, timeout=10)
            lines = result.stdout.strip().split('\n')
            
            devices = []
            for line in lines[1:]:
                if '\t' in line:
                    device_id, status = line.split('\t')
                    if status.strip() == 'device':
                        devices.append(device_id)
            
            if not devices:
                QMessageBox.warning(parent_dialog, "No Devices", "No devices connected. Please connect devices first.")
                return
            
            # Show device selection dialog
            device, ok = QInputDialog.getItem(parent_dialog, "Select Device", 
                                             "Choose a device to assign this account:", 
                                             devices, 0, False)
            if ok and device:
                # Use a separate mapping file instead of modifying account_info.json
                import tempfile
                mapping_file = os.path.join(tempfile.gettempdir(), "frt_device_account_mapping.json")
                
                # Load existing mappings
                mappings = {}
                if os.path.exists(mapping_file):
                    try:
                        with open(mapping_file, 'r', encoding='utf-8') as f:
                            mappings = json.load(f)
                    except:
                        mappings = {}
                
                # Get device model
                model_result = safe_subprocess_run([self.adb_path, "-s", device, "shell", "getprop", "ro.product.model"],
                                           capture_output=True, text=True, timeout=5)
                model = model_result.stdout.strip() if model_result.stdout else "Unknown"
                
                # Store mapping: device_id -> {uid, folder_name, model}
                mappings[device] = {
                    'uid': uid,
                    'folder': folder_name,
                    'model': model,
                    'assigned_date': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Save mappings
                with open(mapping_file, 'w', encoding='utf-8') as f:
                    json.dump(mappings, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(parent_dialog, "Success", 
                                      f"Account {uid} assigned to device {device} ({model})")
                parent_dialog.accept()
                self.load_main_account_tab()
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(parent_dialog, "Error", f"Error: {str(e)}")
    

    def copy_account_field(self, row, column):
        """Copy a specific field from account table to clipboard"""
        item = self.account_table.item(row, column)
        if item:
            clipboard = QApplication.clipboard()
            clipboard.setText(item.text())
            QMessageBox.information(self, "Copied", f"Copied to clipboard: {item.text()}", QMessageBox.StandardButton.Ok)


    def close_main_account_tab(self):
        """Close the main Account tab - can be reopened without restart"""
        # Find and remove the tab
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Accounts and Devices":
                self.tab_widget.removeTab(i)
                self.account_tab_index = -1
                # Mark as deleted so it will be recreated when reopened
                self.main_account_tab = None
                break
    

    def filter_main_account_tab(self):
        """Filter accounts in the main account tab — uses in-memory cache, no disk I/O."""
        search_text = self.account_search_input.text().lower()
        category = self.account_category_filter.currentText() if hasattr(self, 'account_category_filter') else "All"
        status = self.account_status_filter.currentText() if hasattr(self, 'account_status_filter') else "All Status"

        # _account_meta_cache is built in _on_load_table_data: uid -> {category, signup_method}
        meta = getattr(self, '_account_meta_cache', {})

        for row in range(self.account_table.rowCount()):
            show_row = True

            if search_text:
                uid    = self.account_table.item(row, 1).text().lower() if self.account_table.item(row, 1) else ""
                email  = self.account_table.item(row, 3).text().lower() if self.account_table.item(row, 3) else ""
                phone  = self.account_table.item(row, 4).text().lower() if self.account_table.item(row, 4) else ""
                name   = self.account_table.item(row, 5).text().lower() if self.account_table.item(row, 5) else ""
                if search_text not in uid and search_text not in email and search_text not in phone and search_text not in name:
                    show_row = False

            if show_row and status != "All Status":
                status_item = self.account_table.item(row, 8)
                row_status = status_item.text() if status_item else ""
                if status == "Active" and row_status != "Active":
                    show_row = False
                elif status == "Idle" and row_status != "Idle":
                    show_row = False

            if show_row and category not in ("All", "---"):
                uid_item = self.account_table.item(row, 1)
                uid_val = uid_item.text() if uid_item else ""
                if uid_val and uid_val != "—":
                    m = meta.get(uid_val, {})
                    if category == "Email":
                        show_row = m.get('signup_method', 'email') == 'email'
                    elif category == "Phone":
                        show_row = m.get('signup_method', 'email') == 'phone'
                    else:
                        show_row = m.get('category', '') == category

            self.account_table.setRowHidden(row, not show_row)

        self.update_account_stats()
    

    def load_accounts_in_table(self, account_table, category_filter, status_filter, account_search_input):
        """Load all accounts from backup folder into a specific table"""
        try:
            backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")
            
            if not os.path.exists(backup_folder):
                account_table.setRowCount(0)
                return
            
            # Get all account folders
            account_folders = [f for f in os.listdir(backup_folder) 
                             if os.path.isdir(os.path.join(backup_folder, f))]
            
            # Store all accounts for filtering (attach to the table widget)
            all_accounts = []
            
            for folder in account_folders:
                json_file = os.path.join(backup_folder, folder, "account_info.json")
                if os.path.exists(json_file):
                    try:
                        with open(json_file, 'r', encoding='utf-8-sig') as f:
                            account_data = json.load(f)
                            all_accounts.append(account_data)
                    except Exception as e:
                        print(f"Error loading {json_file}: {e}")
            
            # Store accounts in the table widget for later filtering
            account_table.setProperty("all_accounts", all_accounts)
            
            # Apply filters and display
            self.filter_accounts_in_table(account_table, category_filter, status_filter, account_search_input)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load accounts: {e}")
    

    def filter_accounts_in_table(self, account_table, category_filter, status_filter, account_search_input):
        """Filter and display accounts based on selected filters in a specific table"""
        try:
            all_accounts = account_table.property("all_accounts")
            if not all_accounts:
                return
            
            category = category_filter.currentText()
            status = status_filter.currentText()
            search_text = account_search_input.text().lower().strip()
            
            # Filter accounts
            filtered_accounts = []
            for account in all_accounts:
                # Category filter
                if category != "All" and category != "---":
                    # Check if it's a default category (Email/Phone) or custom category
                    if category == "Email":
                        signup_method = account.get('signup_method', 'email')
                        if signup_method != "email":
                            continue
                    elif category == "Phone":
                        signup_method = account.get('signup_method', 'email')
                        if signup_method != "phone":
                            continue
                    else:
                        # Custom category
                        account_category = account.get('category', '')
                        if account_category != category:
                            continue
                
                # Status filter
                if status != "All":
                    account_status = account.get('status', '')
                    if status == "Pending SMS" and "sms" not in account_status.lower():
                        continue
                    if status == "Pending Email" and "email" not in account_status.lower():
                        continue
                    if status == "Active" and account_status != "active":
                        continue
                    if status == "Suspended" and account_status != "suspended":
                        continue
                
                # Search filter
                if search_text:
                    searchable_fields = [
                        account.get('account_uid', account.get('uid', '')),
                        account.get('full_name', account.get('name', '')),
                        account.get('first_name', ''),
                        account.get('last_name', ''),
                        account.get('email', ''),
                        account.get('phone', ''),
                        account.get('password', ''),
                        account.get('device_info', {}).get('model', ''),
                        account.get('device_info', {}).get('device_name_short', ''),
                    ]
                    
                    # Check if search text is in any of the searchable fields
                    if not any(search_text in str(field).lower() for field in searchable_fields):
                        continue
                
                filtered_accounts.append(account)
            
            # Display filtered accounts
            account_table.setRowCount(len(filtered_accounts))
            
            for row, account in enumerate(filtered_accounts):
                # # (Row Number)
                num_item = QTableWidgetItem(str(row + 1))
                num_item.setForeground(QColor("#888888"))  # Gray for row number
                num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                account_table.setItem(row, 0, num_item)
                
                # UID
                uid_item = QTableWidgetItem(account.get('account_uid', account.get('uid', 'N/A')))
                uid_item.setForeground(QColor("#FFD700"))  # Gold color for UID
                account_table.setItem(row, 1, uid_item)
                
                # Name
                account_table.setItem(row, 2, QTableWidgetItem(account.get('full_name', account.get('name', ''))))
                
                # Email
                account_table.setItem(row, 3, QTableWidgetItem(account.get('email', '')))
                
                # Phone
                account_table.setItem(row, 4, QTableWidgetItem(account.get('phone', '')))
                
                # Password
                password_item = QTableWidgetItem(account.get('password', ''))
                password_item.setForeground(QColor("#FF9800"))  # Orange for password
                account_table.setItem(row, 5, password_item)
                
                # Birthday
                account_table.setItem(row, 6, QTableWidgetItem(account.get('birthday', '')))
                
                # Gender
                gender_item = QTableWidgetItem(account.get('gender', ''))
                if account.get('gender', '').lower() == 'male':
                    gender_item.setForeground(QColor("#2196F3"))  # Blue for male
                elif account.get('gender', '').lower() == 'female':
                    gender_item.setForeground(QColor("#E91E63"))  # Pink for female
                account_table.setItem(row, 7, gender_item)
                
                # Device
                # First check cache file for device assignment
                device_serial = ''
                try:
                    import tempfile
                    cache_file = os.path.join(tempfile.gettempdir(), "frt_device_cache.json")
                    if os.path.exists(cache_file):
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            device_cache = json.load(f)
                            uid = account.get('account_uid', account.get('uid', ''))
                            if uid in device_cache:
                                device_serial = device_cache[uid].get('device_serial', '')
                except:
                    pass
                
                # Fallback to account data if not in cache
                if not device_serial:
                    device_serial = account.get('device_serial', '')
                
                if device_serial:
                    device_text = device_serial
                else:
                    device_text = ""
                # device column set below after status (with color)
                
                # Status
                # First check cache file for status
                status_text = ''
                try:
                    import tempfile
                    cache_file = os.path.join(tempfile.gettempdir(), "frt_device_cache.json")
                    if os.path.exists(cache_file):
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            device_cache = json.load(f)
                            uid = account.get('account_uid', account.get('uid', ''))
                            if uid in device_cache:
                                status_text = device_cache[uid].get('status', '')
                except:
                    pass
                
                # Fallback to account data if not in cache
                if not status_text:
                    status_text = account.get('status', 'unknown')
                
                status_item = QTableWidgetItem(status_text)
                if 'pending' in status_text.lower():
                    status_item.setForeground(QColor("#FF9800"))
                elif 'active' in status_text.lower():
                    status_item.setForeground(QColor("#4CAF50"))
                elif 'suspended' in status_text.lower():
                    status_item.setForeground(QColor("#f44336"))
                elif 'device assigned' in status_text.lower() and getattr(self, 'devices_loaded', False):
                    status_item.setForeground(QColor("#4CAF50"))
                account_table.setItem(row, 9, status_item)

                # Device column - green only after user clicks Load Devices
                device_item = QTableWidgetItem(device_text)
                if device_text and getattr(self, 'devices_loaded', False):
                    device_item.setForeground(QColor("#4CAF50"))
                account_table.setItem(row, 8, device_item)
                
                # Proxy
                # Check cache for proxy info
                proxy_text = ''
                try:
                    import tempfile
                    cache_file = os.path.join(tempfile.gettempdir(), "frt_device_cache.json")
                    if os.path.exists(cache_file):
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            device_cache = json.load(f)
                            uid = account.get('account_uid', account.get('uid', ''))
                            if uid in device_cache:
                                proxy_text = device_cache[uid].get('proxy', '')
                except:
                    pass
                
                proxy_item = QTableWidgetItem(proxy_text)
                if proxy_text:
                    proxy_item.setForeground(QColor("#4CAF50"))  # Green if connected
                else:
                    proxy_item.setForeground(QColor("#888888"))  # Gray if not connected
                account_table.setItem(row, 10, proxy_item)
                
                # Created
                created_at = account.get('created_at', '')
                account_table.setItem(row, 11, QTableWidgetItem(created_at))
                
                # Notes
                notes = account.get('notes', '')
                notes_item = QTableWidgetItem(notes)
                notes_item.setForeground(QColor("#888888"))  # Gray for notes
                account_table.setItem(row, 12, notes_item)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to filter accounts: {e}")
    

    def load_accounts(self):
        """Legacy method - kept for compatibility"""
        pass
    

    def filter_accounts(self):
        """Legacy method - kept for compatibility"""
        pass
    

    def show_account_context_menu(self, position):
        """Show context menu for account table - account operations"""
        _MENU_STYLE = """
            QMenu { background-color: #252526; color: #cccccc; border: 1px solid #3d3d3d;
                border-radius: 6px; padding: 4px; font-size: 12px; }
            QMenu::item { padding: 8px 20px 8px 12px; border-radius: 4px; margin: 1px 2px; }
            QMenu::item:selected { background-color: rgba(76,175,80,0.2); color: #ffffff; }
            QMenu::item:disabled { color: #555555; }
            QMenu::separator { height: 1px; background-color: #3d3d3d; margin: 4px 8px; }
            QMenu QMenu { background-color: #252526; border: 1px solid #3d3d3d; border-radius: 6px; padding: 4px; }
            QMenu::right-arrow { width: 16px; height: 16px; margin-right: 4px; }
        """
        menu = QMenu()
        menu.setStyleSheet(_MENU_STYLE)
        
        # Determine which table triggered the context menu
        sender_table = self.sender()
        if sender_table is None:
            sender_table = self.account_table
        
        # Use the correct table for operations
        active_table = sender_table if sender_table else self.account_table

        # Select row under cursor on right-click ONLY if nothing is selected
        index = active_table.indexAt(position)
        if index.isValid():
            if not active_table.selectionModel().selectedRows():
                active_table.selectRow(index.row())

        selected_rows = active_table.selectionModel().selectedRows()

        # ── Select All ────────────────────────────────────────────────────
        select_all_action = menu.addAction(qta.icon('fa5s.check-double', color='#4CAF50'), "Select All")
        update_data_action = menu.addAction(qta.icon('fa5s.sync-alt', color='#4CAF50'), "Update Data")
        menu.addSeparator()

        # ── Import ────────────────────────────────────────────────────────
        import_menu = menu.addMenu(qta.icon('fa5s.file-import', color='#FF9800'), "Import")
        import_accounts_action = import_menu.addAction(qta.icon('fa5s.file-import', color='#FF9800'), "Import Accounts")
        import_proxy_action = import_menu.addAction(qta.icon('fa5s.file-alt', color='#2196F3'), "Import Proxy")
        import_note_action = import_menu.addAction(qta.icon('fa5s.sticky-note', color='#FFD700'), "Import Note")
        import_menu.addSeparator()
        import_vpn_menu = import_menu.addMenu(qta.icon('fa5s.shield-alt', color='#FF9800'), "Import OpenVPN")
        import_vpn_file_action = import_vpn_menu.addAction("Import .ovpn File")
        import_vpn_folder_action = import_vpn_menu.addAction("Import .ovpn Folder")
        import_wg_menu = import_menu.addMenu(qta.icon('fa5s.shield-alt', color='#f44336'), "Import Wireguard")
        import_wg_file_action = import_wg_menu.addAction("Import .conf File")
        import_wg_folder_action = import_wg_menu.addAction("Import .conf Folder")
        menu.addSeparator()

        # ── Copy ──────────────────────────────────────────────────────────
        copy_menu = menu.addMenu(qta.icon('fa5s.copy', color='#2196F3'), "Copy")
        copy_uid_action = copy_menu.addAction("UID")
        copy_password_action = copy_menu.addAction("Password")
        copy_email_action = copy_menu.addAction("Email")
        copy_phone_action = copy_menu.addAction("Phone")
        copy_cookie_action = copy_menu.addAction("Cookie")
        copy_all_action = copy_menu.addAction("All Info")
        copy_custom_action = copy_menu.addAction("Custom...")
        copy_menu.addSeparator()
        copy_file_menu = copy_menu.addMenu(qta.icon('fa5s.copy', color='#4CAF50'), "File Backup")
        copy_file_device_action = copy_file_menu.addAction("Device Info")
        copy_file_profile_action = copy_file_menu.addAction("Profile Info")
        copy_file_all_action = copy_file_menu.addAction("All Files")
        move_menu = menu.addMenu(qta.icon('fa5s.arrow-right', color='#f44336'), "Move File To")
        move_folder_action = move_menu.addAction("Move to Folder...")
        menu.addSeparator()

        # ── Category ──────────────────────────────────────────────────────
        category_menu = menu.addMenu(qta.icon('fa5s.tag', color='#9C27B0'), "Assign Category")
        category_none_action = category_menu.addAction(qta.icon('fa5s.times', color='#f44336'), "None (Remove Category)")
        category_menu.addSeparator()
        # Add custom categories
        custom_categories = self.load_custom_categories()
        category_actions = {}
        for cat in custom_categories:
            cat_action = category_menu.addAction(qta.icon('fa5s.tag', color='#9C27B0'), cat)
            category_actions[cat_action] = cat
        if not custom_categories:
            no_cat_action = category_menu.addAction("No categories available")
            no_cat_action.setEnabled(False)
        menu.addSeparator()

        # ── Check & Sell ──────────────────────────────────────────────────
        check_uid_action = menu.addAction(qta.icon('fa5s.list-ol', color='#2196F3'), "Check Live UID")
        check_backup_action = menu.addAction(qta.icon('fa5s.undo', color='#4CAF50'), "Check Backup")
        get_code_action = menu.addAction(qta.icon('fa5s.envelope', color='#FFD700'), "Get Code Email")
        sell_menu = menu.addMenu(qta.icon('fa5s.arrow-right', color='#FF9800'), "Sell accounts")
        sell_export_action = sell_menu.addAction("Export for Sale")
        sell_format_action = sell_menu.addAction("Format: UID|Pass|Cookie")
        menu.addSeparator()

        # ── Delete ────────────────────────────────────────────────────────
        delete_menu = menu.addMenu(qta.icon('fa5s.times-circle', color='#f44336'), "Delete")
        delete_selected_action = delete_menu.addAction("Delete Selected")
        delete_all_action = delete_menu.addAction("Delete All")
        menu.addSeparator()

        # ── Device Actions ────────────────────────────────────────────────
        clear_recents_action = menu.addAction(qta.icon('fa5s.broom', color='#FF5722'), "Clear Recents")
        menu.addSeparator()

        # ── Manual Login & Open Account ───────────────────────────────────
        manual_login_action = menu.addAction(qta.icon('fa5s.sign-in-alt', color='#4CAF50'), "Manual Login")
        open_account_action = menu.addAction(qta.icon('fa5s.folder-open', color='#2196F3'), "Open Account")
        menu.addSeparator()

        # ── Manual ────────────────────────────────────────────────────────
        # Execute with menu centered on cursor position
        global_pos = active_table.viewport().mapToGlobal(position)
        menu_size = menu.sizeHint()
        centered_pos = QPoint(global_pos.x() - menu_size.width() // 2, global_pos.y() - menu_size.height() // 2)
        action = menu.exec(centered_pos)
        if not action:
            return

        # Get selected UIDs
        rows = active_table.selectionModel().selectedRows()
        uids = [active_table.item(r.row(), 1).text() for r in rows if active_table.item(r.row(), 1)]
        
        if action == select_all_action:
            active_table.selectAll()

        elif action == copy_uid_action:
            QApplication.clipboard().setText('\n'.join(uids))
            self.add_activity(f"Copied {len(uids)} UID(s)")

        elif action == copy_password_action:
            # Get real data from backup files
            vals = []
            for uid in uids:
                account_data = self._get_account_data_by_uid(uid)
                if account_data:
                    vals.append(account_data.get('password', ''))
            QApplication.clipboard().setText('\n'.join(vals))
            self.add_activity(f"Copied {len(vals)} password(s)")

        elif action == copy_email_action:
            # Get real data from backup files
            vals = []
            for uid in uids:
                account_data = self._get_account_data_by_uid(uid)
                if account_data:
                    vals.append(account_data.get('email', ''))
            QApplication.clipboard().setText('\n'.join(vals))
            self.add_activity(f"Copied {len(vals)} email(s)")

        elif action == copy_phone_action:
            # Get real data from backup files
            vals = []
            for uid in uids:
                account_data = self._get_account_data_by_uid(uid)
                if account_data:
                    vals.append(account_data.get('phone', ''))
            QApplication.clipboard().setText('\n'.join(vals))
            self.add_activity(f"Copied {len(vals)} phone(s)")

        elif action == copy_cookie_action:
            # Get real data from backup files
            vals = []
            for uid in uids:
                account_data = self._get_account_data_by_uid(uid)
                if account_data:
                    vals.append(account_data.get('cookies', account_data.get('cookie', '')))
            QApplication.clipboard().setText('\n'.join(vals))
            self.add_activity(f"Copied {len(vals)} cookie(s)")

        elif action == copy_all_action:
            # Get real data from backup files
            lines = []
            for uid in uids:
                account_data = self._get_account_data_by_uid(uid)
                if account_data:
                    password = account_data.get('password', '')
                    email = account_data.get('email', '')
                    phone = account_data.get('phone', '')
                    fname = account_data.get('first_name', '')
                    lname = account_data.get('last_name', '')
                    name = account_data.get('full_name', f"{fname} {lname}".strip())
                    pass_mail = account_data.get('pass_mail', account_data.get('email_password', ''))
                    cookie = account_data.get('cookies', account_data.get('cookie', ''))
                    twofa = account_data.get('2fa', account_data.get('twofa', ''))
                    created = account_data.get('created_at', account_data.get('created_date', ''))
                    parts = [uid, password, email, phone, name, pass_mail, cookie, twofa, created]
                    lines.append('|'.join(parts))
            QApplication.clipboard().setText('\n'.join(lines))
            self.add_activity(f"Copied {len(lines)} account(s)")


        elif action == copy_custom_action:
            # Show dialog to let user choose which columns to copy and format
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QLineEdit, QLabel, QPushButton, QFrame, QGridLayout, QButtonGroup, QRadioButton
            from PyQt6.QtCore import Qt
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Copy Custom Format")
            dialog.setMinimumWidth(500)
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #252526;
                    color: #cccccc;
                }
                QLabel {
                    color: #cccccc;
                    font-size: 13px;
                    font-weight: 500;
                }
                QLabel#title {
                    color: #ffffff;
                    font-size: 14px;
                    font-weight: 600;
                    padding: 4px 0px;
                }
                QLabel#subtitle {
                    color: #888888;
                    font-size: 11px;
                    padding-bottom: 8px;
                }
                QCheckBox {
                    color: #cccccc;
                    font-size: 12px;
                    spacing: 8px;
                    padding: 6px 8px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border: 1px solid #3d3d3d;
                    border-radius: 3px;
                    background-color: #1e1e1e;
                }
                QCheckBox::indicator:checked {
                    background-color: #4CAF50;
                    border-color: #4CAF50;
                    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEzIDRMNiAxMUwzIDgiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
                }
                QCheckBox::indicator:hover {
                    border-color: #4CAF50;
                }
                QRadioButton {
                    color: #cccccc;
                    font-size: 12px;
                    spacing: 8px;
                    padding: 4px 8px;
                }
                QRadioButton::indicator {
                    width: 14px;
                    height: 14px;
                    border: 2px solid #3d3d3d;
                    border-radius: 7px;
                    background-color: #1e1e1e;
                }
                QRadioButton::indicator:checked {
                    background-color: #4CAF50;
                    border-color: #4CAF50;
                }
                QRadioButton::indicator:hover {
                    border-color: #4CAF50;
                }
                QLineEdit {
                    background-color: #1e1e1e;
                    color: #cccccc;
                    border: 1px solid #3d3d3d;
                    padding: 8px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                    selection-background-color: #4CAF50;
                }
                QLineEdit:focus {
                    border: 1px solid #4CAF50;
                    background-color: #2d2d2d;
                }
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 10px 24px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 600;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
                QPushButton#cancel {
                    background-color: #3d3d3d;
                    color: #cccccc;
                }
                QPushButton#cancel:hover {
                    background-color: #4d4d4d;
                }
                QPushButton#cancel:pressed {
                    background-color: #2d2d2d;
                }
                QPushButton#preset {
                    background-color: #2d2d2d;
                    color: #cccccc;
                    padding: 6px 16px;
                    min-width: 60px;
                }
                QPushButton#preset:hover {
                    background-color: #3d3d3d;
                }
                QFrame#separator {
                    background-color: #3d3d3d;
                    max-height: 1px;
                }
            """)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(16)
            layout.setContentsMargins(24, 20, 24, 20)
            
            # Subtitle
            subtitle = QLabel(f"Select columns to copy for {len(rows)} account(s)")
            subtitle.setObjectName("subtitle")
            layout.addWidget(subtitle)
            
            # Separator line
            sep_line = QFrame()
            sep_line.setObjectName("separator")
            sep_line.setFrameShape(QFrame.Shape.HLine)
            layout.addWidget(sep_line)
            
            # Preset buttons
            preset_frame = QFrame()
            preset_layout = QHBoxLayout(preset_frame)
            preset_layout.setContentsMargins(0, 4, 0, 4)
            preset_label = QLabel("Presets:")
            preset_layout.addWidget(preset_label)
            
            essential_btn = QPushButton("Essential")
            essential_btn.setObjectName("preset")
            full_btn = QPushButton("Full")
            full_btn.setObjectName("preset")
            custom_btn = QPushButton("Custom")
            custom_btn.setObjectName("preset")
            
            preset_layout.addWidget(essential_btn)
            preset_layout.addWidget(full_btn)
            preset_layout.addWidget(custom_btn)
            preset_layout.addStretch()
            layout.addWidget(preset_frame)
            
            # Column checkboxes in grid layout (3 columns)
            checkbox_frame = QFrame()
            checkbox_layout = QGridLayout(checkbox_frame)
            checkbox_layout.setSpacing(8)
            checkbox_layout.setContentsMargins(0, 8, 0, 8)
            
            column_names = ["UID", "Password", "Email", "Phone", "2FA", "Token", "Cookie", "Name", "Pass/Mail", "Created", "Birthday", "Gender", "Notes", "Status"]
            checkboxes = []
            for i, col_name in enumerate(column_names):
                cb = QCheckBox(col_name)
                # Default to Essential preset (UID, Password, Email, 2FA, Token, Cookie)
                cb.setChecked(col_name in ["UID", "Password", "Email", "2FA", "Token", "Cookie"])
                checkboxes.append(cb)
                row = i // 3
                col = i % 3
                checkbox_layout.addWidget(cb, row, col)
            
            layout.addWidget(checkbox_frame)
            
            # Preset button handlers
            def set_essential():
                essential_cols = ["UID", "Password", "Email", "2FA", "Token", "Cookie"]
                for i, col_name in enumerate(column_names):
                    checkboxes[i].setChecked(col_name in essential_cols)
            
            def set_full():
                for cb in checkboxes:
                    cb.setChecked(True)
            
            def set_custom():
                # Just enable all checkboxes for manual selection
                pass
            
            essential_btn.clicked.connect(set_essential)
            full_btn.clicked.connect(set_full)
            custom_btn.clicked.connect(set_custom)
            
            # Skip empty fields option
            skip_empty_frame = QFrame()
            skip_empty_layout = QHBoxLayout(skip_empty_frame)
            skip_empty_layout.setContentsMargins(0, 8, 0, 0)
            skip_empty_cb = QCheckBox("Skip empty fields (intelligent output)")
            skip_empty_cb.setChecked(True)
            skip_empty_cb.setStyleSheet("color: #4CAF50; font-weight: 600;")
            skip_empty_layout.addWidget(skip_empty_cb)
            skip_empty_layout.addStretch()
            layout.addWidget(skip_empty_frame)
            
            # Separator input
            sep_frame = QFrame()
            sep_layout = QHBoxLayout(sep_frame)
            sep_layout.setContentsMargins(0, 8, 0, 0)
            sep_label = QLabel("Separator:")
            sep_label.setMinimumWidth(80)
            sep_layout.addWidget(sep_label)
            sep_input = QLineEdit("|")
            sep_input.setMaximumWidth(150)
            sep_input.setPlaceholderText("e.g., | or , or ;")
            sep_layout.addWidget(sep_input)
            sep_layout.addStretch()
            layout.addWidget(sep_frame)
            
            # Separator line
            sep_line2 = QFrame()
            sep_line2.setObjectName("separator")
            sep_line2.setFrameShape(QFrame.Shape.HLine)
            layout.addWidget(sep_line2)
            
            # Buttons
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(12)
            btn_layout.addStretch()
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setObjectName("cancel")
            ok_btn = QPushButton("Copy to Clipboard")
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addWidget(cancel_btn)
            btn_layout.addWidget(ok_btn)
            layout.addLayout(btn_layout)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Get selected column names
                selected_col_names = [column_names[i] for i, cb in enumerate(checkboxes) if cb.isChecked()]
                separator = sep_input.text()
                skip_empty = skip_empty_cb.isChecked()
                
                if not selected_col_names:
                    self.add_activity("⚠ No columns selected")
                    return
                
                # Map column names to data keys
                col_map = {
                    "UID": "uid",
                    "Password": "password",
                    "Email": "email",
                    "Phone": "phone",
                    "Name": "name",
                    "Pass/Mail": "pass_mail",
                    "Cookie": "cookie",
                    "2FA": "twofa",
                    "Token": "token",
                    "Created": "created",
                    "Birthday": "birthday",
                    "Gender": "gender",
                    "Notes": "notes",
                    "Status": "status"
                }
                
                lines = []
                for uid in uids:
                    account_data = self._get_account_data_by_uid(uid)
                    if account_data:
                        parts = []
                        for col_name in selected_col_names:
                            key = col_map.get(col_name)
                            value = ""
                            
                            if key == "uid":
                                value = uid
                            elif key == "password":
                                value = account_data.get('password', '')
                            elif key == "email":
                                value = account_data.get('email', '')
                            elif key == "phone":
                                value = account_data.get('phone', '')
                            elif key == "name":
                                fname = account_data.get('first_name', '')
                                lname = account_data.get('last_name', '')
                                value = account_data.get('full_name', f"{fname} {lname}".strip())
                            elif key == "pass_mail":
                                value = account_data.get('pass_mail', account_data.get('email_password', ''))
                            elif key == "cookie":
                                value = account_data.get('cookies', account_data.get('cookie', ''))
                            elif key == "twofa":
                                value = account_data.get('2fa', account_data.get('twofa', ''))
                            elif key == "token":
                                value = account_data.get('token', '')
                            elif key == "created":
                                value = account_data.get('created_at', account_data.get('created_date', ''))
                            elif key == "birthday":
                                value = account_data.get('birthday', '')
                            elif key == "gender":
                                value = account_data.get('gender', '')
                            elif key == "notes":
                                value = account_data.get('notes', '')
                            elif key == "status":
                                value = account_data.get('status', '')
                            
                            # Skip empty fields if option is enabled
                            if skip_empty and not value:
                                continue
                            
                            parts.append(value)
                        
                        lines.append(separator.join(parts))
                
                QApplication.clipboard().setText('\n'.join(lines))
                mode_text = "intelligent" if skip_empty else "custom"
                self.add_activity(f"✓ Copied {len(lines)} account(s) with {mode_text} format")

        # ── Category Assignment ───────────────────────────────────────────
        elif action == category_none_action:
            # Remove category from selected accounts
            self.assign_category_to_accounts(selected_rows, "")
        elif action in category_actions:
            # Assign selected category to accounts
            selected_category = category_actions[action]
            self.assign_category_to_accounts(selected_rows, selected_category)

        elif action == import_accounts_action:
            self.open_import_tab()

        elif action == import_proxy_action:
            path, _ = QFileDialog.getOpenFileName(self, "Import Proxy File", "", "Text Files (*.txt);;All Files (*)")
            if path:
                self.add_activity(f"Proxy file selected: {path}")

        elif action == update_data_action:
            self.load_main_account_tab()
            self.add_activity("Account data refreshed")

        elif action == delete_selected_action:
            if not uids:
                self.add_activity("⚠ No accounts selected")
                return
            reply = QMessageBox.question(self, "Confirm Delete",
                f"Delete {len(uids)} account(s)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                deleted = 0
                folders_to_delete = []
                
                # First pass: identify folders to delete (without keeping files open)
                _backup_root = os.path.join(_PROJECT_ROOT, "account_backup")
                if os.path.exists(_backup_root):
                    for folder_name in os.listdir(_backup_root):
                        folder_path = os.path.join(_backup_root, folder_name)
                        if os.path.isdir(folder_path):
                            account_info_path = os.path.join(folder_path, "account_info.json")
                            if os.path.exists(account_info_path):
                                try:
                                    with open(account_info_path, 'r', encoding='utf-8') as f:
                                        data = json.load(f)
                                    # File is now closed
                                    acct_uid = data.get('account_uid', data.get('uid', ''))
                                    if acct_uid in uids:
                                        folders_to_delete.append((folder_path, acct_uid))
                                except Exception as e:
                                    self.add_activity(f"✗ Error reading {folder_name}: {e}")
                
                # Second pass: delete the folders
                import shutil
                for folder_path, acct_uid in folders_to_delete:
                    try:
                        shutil.rmtree(folder_path)
                        deleted += 1
                        self.add_activity(f"✓ Deleted account {acct_uid}")
                    except Exception as e:
                        self.add_activity(f"✗ Error deleting {acct_uid}: {e}")
                
                self.add_activity(f"✓ Deleted {deleted} of {len(uids)} account(s)")
                
                # Reload the account tab to reflect changes
                self.load_main_account_tab()
                
                # Update dashboard statistics
                if hasattr(self, 'total_accounts'):
                    _ab = os.path.join(_PROJECT_ROOT, "account_backup")
                    self.total_accounts = len([f for f in os.listdir(_ab) if os.path.isdir(os.path.join(_ab, f))]) if os.path.exists(_ab) else 0
                    if hasattr(self, 'update_statistics_display'):
                        self.update_statistics_display()
            else:
                self.add_activity("Delete cancelled")

        elif action == check_uid_action:
            self.add_activity(f"Checking {len(uids)} UID(s)...")

        elif action == clear_recents_action:
            for r in rows:
                device_item = self.account_table.item(r.row(), 1)
                if device_item:
                    device_id = device_item.text().strip()
                    if device_id and device_id != "—":
                        self._clear_recents_single(device_id)

        elif action == manual_login_action:
            self.open_login_tab()

        elif action == open_account_action:
            for uid in uids:
                self.add_activity(f"Opening account {uid}...")
    

    def _show_copy_custom_dialog(self):
        """Show dialog to select custom fields to copy"""
        selected_rows = self.account_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Copy Custom Fields")
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 12px;
            }
            QCheckBox {
                color: #e0e0e0;
                font-size: 12px;
                padding: 4px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #555555;
                background-color: transparent;
            }
            QCheckBox::indicator:hover {
                border-color: #4CAF50;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border-color: #4CAF50;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border-color: #4CAF50;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Select fields to copy:")
        title.setStyleSheet("color: #4CAF50; font-size: 13px; font-weight: bold;")
        layout.addWidget(title)
        
        # Checkboxes for each field
        fields = [
            ("UID", 1),
            ("Name", 2),
            ("Email", 3),
            ("Phone", 4),
            ("Password", 5),
            ("Birthday", 6),
            ("Gender", 7),
            ("Device", 8),
            ("Status", 9),
            ("Proxy", 10),
            ("Created", 11),
            ("Notes", 12)
        ]
        
        checkboxes = {}
        for field_name, col_idx in fields:
            cb = QCheckBox(field_name)
            cb.setChecked(True)  # All checked by default
            checkboxes[field_name] = (cb, col_idx)
            layout.addWidget(cb)
        
        layout.addSpacing(10)
        
        # Format options
        format_label = QLabel("Format:")
        format_label.setStyleSheet("color: #4CAF50; font-size: 12px; font-weight: bold;")
        layout.addWidget(format_label)
        
        format_group = QWidget()
        format_layout = QVBoxLayout(format_group)
        format_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.setSpacing(4)
        

    def _get_devices_from_selection(self):
        """Get device IDs from selected device rows (device-centric table)."""
        # Check if we have a temporary single device (from context menu)
        if hasattr(self, '_temp_single_device') and self._temp_single_device:
            devices = self._temp_single_device
            self._temp_single_device = None  # Clear it after use
            return devices
        
        selected_rows = self.account_table.selectionModel().selectedRows()
        if not selected_rows:
            return []
        
        devices = []
        for row_idx in selected_rows:
            row = row_idx.row()
            # In device-centric table, column 1 is Device ID
            device_item = self.account_table.item(row, 1)
            if device_item and device_item.text().strip():
                device_id = device_item.text().strip()
                if device_id and device_id not in devices and device_id != "No devices loaded — click 'Load Devices' to select devices":
                    devices.append(device_id)

        # Also include the right-clicked row in case it wasn't in selection
        current = self.account_table.currentIndex()
        if current.isValid():
            row = current.row()
            device_item = self.account_table.item(row, 1)
            if device_item and device_item.text().strip():
                device_id = device_item.text().strip()
                if device_id and device_id not in devices and device_id != "No devices loaded — click 'Load Devices' to select devices":
                    devices.append(device_id)

        return devices
    

    def _get_account_data_by_uid(self, uid):
        """Get account data from backup folder by UID."""
        if not os.path.exists("account_backup"):
            return None
        
        for folder_name in os.listdir("account_backup"):
            folder_path = os.path.join("account_backup", folder_name)
            if os.path.isdir(folder_path):
                account_info_path = os.path.join(folder_path, "account_info.json")
                if os.path.exists(account_info_path):
                    try:
                        with open(account_info_path, 'r', encoding='utf-8') as f:
                            account_data = json.load(f)
                            stored_uid = account_data.get('account_uid', account_data.get('uid', account_data.get('id', folder_name.split('_')[0])))
                            if stored_uid == uid:
                                return account_data
                    except:
                        pass
        return None
        format_layout.addWidget(format_labeled)
        
        format_values_only = QRadioButton("Values only (separated by |)")
        format_values_only.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        format_layout.addWidget(format_values_only)
        
        layout.addWidget(format_group)
        layout.addSpacing(10)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: [cb.setChecked(True) for cb, _ in checkboxes.values()])
        btn_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: [cb.setChecked(False) for cb, _ in checkboxes.values()])
        btn_layout.addWidget(deselect_all_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        copy_btn = QPushButton("Copy")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        copy_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(copy_btn)
        
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get selected row data
            row = selected_rows[0].row()
            
            # Collect selected fields
            info_parts = []
            for field_name, (cb, col_idx) in checkboxes.items():
                if cb.isChecked():
                    item = self.account_table.item(row, col_idx)
                    if item:
                        value = item.text().strip()
                        if value:
                            if format_labeled.isChecked():
                                info_parts.append(f"{field_name}: {value}")
                            else:
                                info_parts.append(value)
            
            if info_parts:
                if format_labeled.isChecked():
                    result = "\n".join(info_parts)
                else:
                    result = " | ".join(info_parts)
                
                QApplication.clipboard().setText(result)
                self.add_activity(f"Copied {len(info_parts)} custom fields to clipboard")
    

    def _load_devices_to_table(self):
        """Load connected ADB devices and distribute them across accounts."""
        self.add_activity("Loading devices...")
        try:
            result = subprocess.run(
                [self.adb_path, 'devices'],
                capture_output=True,
                text=True,
                timeout=5,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode != 0:
                self.add_activity("Failed to get device list")
                return
            
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            devices = []
            device_info = {}  # Map serial to model name
            
            for line in lines:
                line = line.strip()
                if line and line.endswith('device'):
                    device_id = line.split()[0]
                    devices.append(device_id)
                    
                    # Get device model name
                    try:
                        model_result = subprocess.run(
                            [self.adb_path, '-s', device_id, 'shell', 'getprop ro.product.model'],
                            capture_output=True,
                            text=True,
                            timeout=3,
                            encoding='utf-8',
                            errors='ignore'
                        )
                        model_name = model_result.stdout.strip() if model_result.returncode == 0 else device_id
                        device_info[device_id] = f"{device_id} ({model_name})" if model_name else device_id
                    except:
                        device_info[device_id] = device_id
            
            if not devices:
                self.add_activity("No devices found")
                return
            
            # Always update ALL rows regardless of selection
            rows_to_update = list(range(self.account_table.rowCount()))
            
            if not rows_to_update:
                self.add_activity("No accounts in table")
                return
            
            # Distribute devices across accounts (round-robin)
            device_count = 0
            for idx, row in enumerate(rows_to_update):
                device_id = devices[idx % len(devices)]  # Cycle through devices
                display_name = device_info.get(device_id, device_id)
                
                # Set Device column (index 8) with format: SERIAL (Model Name)
                dev_item = QTableWidgetItem(display_name)
                dev_item.setForeground(QColor("#4CAF50"))
                self.account_table.setItem(row, 8, dev_item)
                # Set Status column (index 9)
                status_item = QTableWidgetItem("Device Assigned")
                status_item.setForeground(QColor("#4CAF50"))
                self.account_table.setItem(row, 9, status_item)
                device_count += 1
                
                # Save device assignment to cache
                uid_item = self.account_table.item(row, 1)  # UID is now column 1
                if uid_item:
                    uid = uid_item.text()
                    
                    # FIRST: Find proxy for THIS device BEFORE updating cache
                    # Search all UIDs to find if this device_id has a proxy
                    proxy_text = ''
                    try:
                        import tempfile
                        cache_file = os.path.join(tempfile.gettempdir(), "frt_device_cache.json")
                        if os.path.exists(cache_file):
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                device_cache = json.load(f)
                                # Search all UIDs to find if this device has a proxy
                                for cached_uid, cached_data in device_cache.items():
                                    cached_device = cached_data.get('device_serial', '')
                                    # Check if this is the same device (by serial number)
                                    if cached_device.startswith(device_id):
                                        proxy_text = cached_data.get('proxy', '')
                                        break
                    except:
                        pass
                    
                    # THEN: Update device assignment in cache (this will change device_serial for this UID)
                    self._update_account_device_in_backup(uid, display_name, "Device Assigned")
                    
                    # FINALLY: If we found a proxy, we need to update it in the NEW UID's cache entry
                    if proxy_text:
                        try:
                            cache_file = os.path.join(tempfile.gettempdir(), "frt_device_cache.json")
                            if os.path.exists(cache_file):
                                with open(cache_file, 'r', encoding='utf-8') as f:
                                    device_cache = json.load(f)
                                if uid in device_cache:
                                    device_cache[uid]['proxy'] = proxy_text
                                    with open(cache_file, 'w', encoding='utf-8') as f:
                                        json.dump(device_cache, f, indent=2, ensure_ascii=False)
                        except:
                            pass
                        
                        # Set proxy in table
                        proxy_item = QTableWidgetItem(proxy_text)
                        proxy_item.setForeground(QColor("#4CAF50"))
                        self.account_table.setItem(row, 10, proxy_item)
            
            self.add_activity(f"Assigned {len(devices)} device(s) to {device_count} account(s)")
            self.devices_loaded = True
            
            # Update dashboard device count label and cache so monitor timer stays in sync
            if hasattr(self, 'device_count_label'):
                self.device_count_label.setText(f"{len(devices)} detected")
            self.device_count_cache = len(devices)
            self.device_count_last_check = time.time()  # Reset timer so it doesn't overwrite immediately
            
            # Also update the device table in the Accounts-only tab if open
            if hasattr(self, '_accounts_only_device_table'):
                try:
                    self._load_devices_only_table(self._accounts_only_device_table)
                    if hasattr(self, '_devices_count_label'):
                        self._devices_count_label.setText(f"{self._accounts_only_device_table.rowCount()} devices")
                except RuntimeError:
                    pass

            # Also refresh the device list in Settings tab
            self.refresh_devices()
            
        except Exception as e:
            self.add_activity(f"Error loading devices: {e}")
    

    def _update_account_device_in_backup(self, uid, device_text, status):
        """Update device and status in a separate cache file."""
        import tempfile
        try:
            # Use temp directory which always has write permissions
            cache_file = os.path.join(tempfile.gettempdir(), "frt_device_cache.json")
            
            # Load existing cache
            device_cache = {}
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        device_cache = json.load(f)
                except:
                    device_cache = {}
            
            # Update cache - preserve existing proxy if it exists
            if uid not in device_cache:
                device_cache[uid] = {}
            
            device_cache[uid]['device_serial'] = device_text
            device_cache[uid]['status'] = status
            # Don't overwrite proxy field if it exists
            
            # Save cache
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(device_cache, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            print(f"Error updating device cache: {e}")
    

    def _set_wallpaper_with_order(self):
        """Generate wallpaper with logo and order number, then set it on selected devices."""
        import threading
        from PIL import Image, ImageDraw, ImageFont
        import tempfile
        import time
        import json
        
        # Get devices from temp storage or from selection
        devices = getattr(self, '_temp_devices_for_wallpaper', None)
        if devices:
            delattr(self, '_temp_devices_for_wallpaper')
        else:
            devices = self._get_devices_from_selection()
        
        if not devices:
            QMessageBox.warning(self, "No Selection", "Please select devices from the device table.")
            return
        
        # Check if manual number was specified (single device)
        manual_number = getattr(self, '_temp_wallpaper_number', None)
        if manual_number:
            delattr(self, '_temp_wallpaper_number')  # Clear after use
        
        # Check if range was specified (multiple devices)
        wallpaper_range = getattr(self, '_temp_wallpaper_range', None)
        if wallpaper_range is not None:
            delattr(self, '_temp_wallpaper_range')  # Clear after use
        
        self.add_activity(f"Setting wallpaper for {len(devices)} device(s)...")
        
        def _run():
            adb = self.adb_path
            logo_path = os.path.join(_PROJECT_ROOT, "logo", "logo.png")
            
            if not os.path.exists(logo_path):
                self.add_activity("ERROR: logo.png not found in logo/ folder")
                return
            
            # Load or create persistent device numbering (only if not manual/range)
            device_map_file = os.path.join(tempfile.gettempdir(), "frt_device_numbers.json")
            device_numbers = {}
            
            if not manual_number and wallpaper_range is None and os.path.exists(device_map_file):
                try:
                    with open(device_map_file, 'r') as f:
                        device_numbers = json.load(f)
                except:
                    pass
            
            # Get ALL connected devices (only if not manual/range)
            if not manual_number and wallpaper_range is None:
                result = subprocess.run(
                    [adb, 'devices'],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='ignore'
                )
                
                all_devices = []
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]
                    for line in lines:
                        line = line.strip()
                        if line and line.endswith('device'):
                            device_id = line.split()[0]
                            all_devices.append(device_id)
                
                # Assign numbers to new devices
                existing_numbers = set(device_numbers.values())
                next_number = 1
                
                for device_id in sorted(all_devices):  # Sort for consistency
                    if device_id not in device_numbers:
                        # Find next available number
                        while next_number in existing_numbers:
                            next_number += 1
                        device_numbers[device_id] = next_number
                        existing_numbers.add(next_number)
                        next_number += 1
                
                # Save updated mapping
                try:
                    with open(device_map_file, 'w') as f:
                        json.dump(device_numbers, f, indent=2)
                except:
                    pass
            
            # Process each device
            for idx, device_id in enumerate(devices):
                # Get the number for this device
                if manual_number:
                    # Single device with manual number
                    device_number = manual_number
                elif wallpaper_range is not None:
                    # Multiple devices with range (from, to)
                    from_num, to_num = wallpaper_range
                    device_number = from_num + idx
                else:
                    # Auto-assign from saved mapping
                    device_number = device_numbers.get(device_id, 1)
                
                try:
                    # Load logo
                    logo = Image.open(logo_path)
                    
                    # Create modern clean wallpaper with smooth gradient (1080x1920)
                    wallpaper = Image.new('RGB', (1080, 1920), color='#0a0a0a')
                    
                    # Modern smooth gradient - dark with subtle color shift
                    import math
                    
                    for y in range(1920):
                        for x in range(1080):
                            # Subtle diagonal gradient
                            factor = (x + y) / (1080 + 1920)
                            
                            # Dark with subtle blue-green tint
                            r = int(8 + factor * 6)
                            g = int(10 + factor * 8)
                            b = int(15 + factor * 10)
                            
                            wallpaper.putpixel((x, y), (r, g, b))
                    
                    draw = ImageDraw.Draw(wallpaper, 'RGBA')
                    
                    # Modern accent - gradient bar at top
                    for i in range(4):
                        alpha = int(255 * (1 - i / 4))
                        draw.rectangle([(0, i), (1080, i + 1)], fill=(76, 175, 80, alpha))
                    
                    # Add subtle geometric elements - modern but minimal
                    # Thin diagonal lines for depth
                    line_color = (76, 175, 80, 20)
                    draw.line([(0, 600), (1080, 800)], fill=line_color, width=1)
                    draw.line([(0, 1200), (1080, 1400)], fill=line_color, width=1)
                    
                    # Modern "FRT" text with clean styling
                    try:
                        font_frt = ImageFont.truetype("arialbd.ttf", 90)
                    except:
                        try:
                            font_frt = ImageFont.truetype("arial.ttf", 90)
                        except:
                            font_frt = ImageFont.load_default()
                    
                    frt_text = "FRT"
                    bbox_frt = draw.textbbox((0, 0), frt_text, font=font_frt)
                    frt_width = bbox_frt[2] - bbox_frt[0]
                    frt_x = (1080 - frt_width) // 2
                    frt_y = 100
                    
                    # Modern subtle glow - just enough
                    for offset in range(8, 0, -2):
                        alpha = int(120 * (offset / 8))
                        draw.text((frt_x - offset//2, frt_y - offset//2), frt_text, 
                                 fill=(76, 175, 80, alpha), font=font_frt)
                    
                    # Clean shadow
                    draw.text((frt_x + 2, frt_y + 2), frt_text, fill=(0, 0, 0, 150), font=font_frt)
                    
                    # Main text - white
                    draw.text((frt_x, frt_y), frt_text, fill='#FFFFFF', font=font_frt)
                    
                    # Modern subtitle with line
                    try:
                        font_subtitle = ImageFont.truetype("arial.ttf", 18)
                    except:
                        font_subtitle = ImageFont.load_default()
                    
                    subtitle = "FACEBOOK REGISTER TOOL"
                    bbox_sub = draw.textbbox((0, 0), subtitle, font=font_subtitle)
                    sub_width = bbox_sub[2] - bbox_sub[0]
                    sub_x = (1080 - sub_width) // 2
                    sub_y = frt_y + 110
                    
                    # Decorative line before subtitle
                    line_y = sub_y + 10
                    draw.line([(sub_x - 40, line_y), (sub_x - 10, line_y)], fill=(76, 175, 80, 200), width=2)
                    draw.line([(sub_x + sub_width + 10, line_y), (sub_x + sub_width + 40, line_y)], fill=(76, 175, 80, 200), width=2)
                    
                    draw.text((sub_x + 1, sub_y + 1), subtitle, fill=(0, 0, 0, 120), font=font_subtitle)
                    draw.text((sub_x, sub_y), subtitle, fill=(160, 160, 160, 255), font=font_subtitle)
                    
                    # Resize logo
                    logo_width = 520
                    logo_height = int(logo.height * (logo_width / logo.width))
                    logo_resized = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
                    
                    # Center logo
                    logo_x = (1080 - logo_width) // 2
                    logo_y = (1920 - logo_height) // 2 - 100
                    
                    # Modern minimal card - just outline
                    card_padding = 50
                    card_x1 = logo_x - card_padding
                    card_y1 = logo_y - card_padding
                    card_x2 = logo_x + logo_width + card_padding
                    card_y2 = logo_y + logo_height + card_padding
                    
                    # Soft shadow
                    for blur in range(20, 0, -4):
                        shadow_alpha = int(60 * (blur / 20))
                        draw.rounded_rectangle(
                            [(card_x1 + blur//2, card_y1 + blur//2), 
                             (card_x2 + blur//2, card_y2 + blur//2)],
                            radius=20, fill=(0, 0, 0, shadow_alpha)
                        )
                    
                    # Green glow around logo area
                    glow_size = 50
                    for i in range(glow_size, 0, -5):
                        alpha = int(120 * (i / glow_size))
                        glow_color = (76, 175, 80, alpha)
                        glow_x1 = card_x1 - i
                        glow_y1 = card_y1 - i
                        glow_x2 = card_x2 + i
                        glow_y2 = card_y2 + i
                        draw.rounded_rectangle(
                            [(glow_x1, glow_y1), (glow_x2, glow_y2)],
                            radius=20 + i, outline=glow_color, width=2
                        )
                    
                    # Modern card outline
                    draw.rounded_rectangle(
                        [(card_x1, card_y1), (card_x2, card_y2)],
                        radius=20, outline=(76, 175, 80, 80), width=2
                    )
                    
                    # Subtle inner glow
                    draw.rounded_rectangle(
                        [(card_x1 + 2, card_y1 + 2), (card_x2 - 2, card_y2 - 2)],
                        radius=18, outline=(76, 175, 80, 40), width=1
                    )
                    
                    # Handle transparency
                    if logo_resized.mode == 'RGBA':
                        wallpaper.paste(logo_resized, (logo_x, logo_y), logo_resized)
                    else:
                        wallpaper.paste(logo_resized, (logo_x, logo_y))
                    
                    # Create new draw object after pasting logo
                    draw = ImageDraw.Draw(wallpaper, 'RGBA')
                    
                    # Modern device number with clean badge
                    order_text = f"#{device_number}"
                    
                    # Use bold font for modern look
                    try:
                        font_large = ImageFont.truetype("arialbd.ttf", 200)
                    except:
                        try:
                            font_large = ImageFont.truetype("arial.ttf", 200)
                        except:
                            font_large = ImageFont.load_default()
                    
                    # Get text size for centering
                    bbox = draw.textbbox((0, 0), order_text, font=font_large)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    text_x = (1080 - text_width) // 2
                    text_y = card_y2 + 70
                    
                    # Modern badge outline
                    badge_padding = 30
                    badge_x1 = text_x - badge_padding
                    badge_y1 = text_y - 10
                    badge_x2 = text_x + text_width + badge_padding
                    badge_y2 = text_y + text_height + 10
                    
                    # Badge shadow
                    for blur in range(15, 0, -3):
                        shadow_alpha = int(80 * (blur / 15))
                        draw.rounded_rectangle(
                            [(badge_x1 + blur//2, badge_y1 + blur//2), 
                             (badge_x2 + blur//2, badge_y2 + blur//2)],
                            radius=15, fill=(0, 0, 0, shadow_alpha)
                        )
                    
                    # Modern badge outline
                    draw.rounded_rectangle(
                        [(badge_x1, badge_y1), (badge_x2, badge_y2)],
                        radius=15, outline=(76, 175, 80, 100), width=2
                    )
                    
                    # Subtle glow
                    for offset in range(10, 0, -2):
                        alpha = int(150 * (offset / 10))
                        draw.text((text_x - offset//2, text_y - offset//2), order_text, 
                                 fill=(76, 175, 80, alpha), font=font_large)
                    
                    # Shadow
                    draw.text((text_x + 3, text_y + 3), order_text, fill=(0, 0, 0, 180), font=font_large)
                    
                    # Main text - white
                    draw.text((text_x, text_y), order_text, fill='#FFFFFF', font=font_large)
                    
                    # Modern label with minimal design
                    try:
                        font_small = ImageFont.truetype("arial.ttf", 22)
                    except:
                        font_small = ImageFont.load_default()
                    
                    label_text = "DEVICE"
                    bbox_label = draw.textbbox((0, 0), label_text, font=font_small)
                    label_width = bbox_label[2] - bbox_label[0]
                    label_x = (1080 - label_width) // 2
                    label_y = badge_y2 + 25
                    
                    # Decorative dots
                    dot_spacing = 8
                    dot_y = label_y + 12
                    draw.ellipse([(label_x - 30, dot_y - 2), (label_x - 26, dot_y + 2)], fill=(76, 175, 80, 200))
                    draw.ellipse([(label_x + label_width + 26, dot_y - 2), (label_x + label_width + 30, dot_y + 2)], fill=(76, 175, 80, 200))
                    
                    # Label text
                    draw.text((label_x + 1, label_y + 1), label_text, fill=(0, 0, 0, 120), font=font_small)
                    draw.text((label_x, label_y), label_text, fill=(140, 140, 140, 255), font=font_small)
                    
                    # Modern corner accents - minimal L shapes
                    corner_size = 50
                    corner_width = 2
                    accent_color = (76, 175, 80, 150)
                    
                    # Top left
                    draw.line([(30, 30), (30 + corner_size, 30)], fill=accent_color, width=corner_width)
                    draw.line([(30, 30), (30, 30 + corner_size)], fill=accent_color, width=corner_width)
                    
                    # Top right
                    draw.line([(1050, 30), (1050 - corner_size, 30)], fill=accent_color, width=corner_width)
                    draw.line([(1050, 30), (1050, 30 + corner_size)], fill=accent_color, width=corner_width)
                    
                    # Bottom left
                    draw.line([(30, 1890), (30 + corner_size, 1890)], fill=accent_color, width=corner_width)
                    draw.line([(30, 1890), (30, 1890 - corner_size)], fill=accent_color, width=corner_width)
                    
                    # Bottom right
                    draw.line([(1050, 1890), (1050 - corner_size, 1890)], fill=accent_color, width=corner_width)
                    draw.line([(1050, 1890), (1050, 1890 - corner_size)], fill=accent_color, width=corner_width)
                    
                    # Save to temp file
                    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                    wallpaper.save(temp_file.name, 'PNG')
                    temp_file.close()
                    
                    # Push to phone
                    safe_subprocess_run([adb, "-s", device_id, "push", temp_file.name, 
                                          "/sdcard/wallpaper.png"], capture_output=True)
                    
                    # Direct method: Copy to system wallpaper location
                    self.add_activity(f"Copying wallpaper to system location...")
                    
                    # Copy to wallpaper file
                    result = safe_subprocess_run([adb, "-s", device_id, "shell",
                        "su -c 'cp /sdcard/wallpaper.png /data/system/users/0/wallpaper'"],
                        capture_output=True)
                    
                    # Copy to wallpaper_orig (backup)
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "su -c 'cp /sdcard/wallpaper.png /data/system/users/0/wallpaper_orig'"],
                        capture_output=True)
                    
                    # Set proper permissions
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "su -c 'chmod 600 /data/system/users/0/wallpaper'"],
                        capture_output=True)
                    
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "su -c 'chmod 600 /data/system/users/0/wallpaper_orig'"],
                        capture_output=True)
                    
                    # Set owner to system
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "su -c 'chown system:system /data/system/users/0/wallpaper*'"],
                        capture_output=True)
                    
                    self.add_activity(f"Restarting SystemUI to apply wallpaper...")
                    
                    # Kill SystemUI to restart it (this applies the wallpaper)
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "su -c 'killall com.android.systemui'"],
                        capture_output=True)
                    
                    time.sleep(2)
                    
                    # Alternative: Restart launcher
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "am broadcast -a android.intent.action.WALLPAPER_CHANGED"],
                        capture_output=True)
                    
                    # Go to home screen to see the wallpaper
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "input keyevent 3"],  # KEYCODE_HOME
                        capture_output=True)
                    
                    # Clean up temp file
                    os.unlink(temp_file.name)
                    
                    self.add_activity(f"✓ Wallpaper set for device {device_id} (#{device_number}) - Press Home to see it")
                    
                except Exception as e:
                    self.add_activity(f"✗ Failed to set wallpaper for device {device_id}: {str(e)}")
            
            self.add_activity(f"Wallpaper setting complete for {len(devices)} device(s)")
            self._show_dialog_signal.emit("Done", f"Wallpaper set for {len(devices)} device(s).\nPress Home on the device to see it.")
        
        threading.Thread(target=_run, daemon=True).start()
    

    def _view_screen(self):
        """Open scrcpy to view device screen."""
        import subprocess
        
        devices = self._get_devices_from_selection()
        if not devices:
            QMessageBox.warning(self, "No Selection", "Please select accounts with assigned devices.")
            return
        
        # Check if scrcpy exists
        scrcpy_path = os.path.join(_PROJECT_ROOT, "scrcpy-win64-v3.1", "scrcpy.exe")
        
        if not os.path.exists(scrcpy_path):
            QMessageBox.warning(self, "scrcpy Not Found", 
                f"scrcpy not found at:\n{scrcpy_path}\n\n"
                "Please ensure scrcpy-win64-v3.1 folder exists in the application directory.")
            return
        
        # Open screen for each selected device
        for device_id in devices:
            self.add_activity(f"Opening screen view for device {device_id}...")
            
            try:
                # Launch scrcpy without console window
                if os.name == 'nt':
                    # Windows: Use CREATE_NO_WINDOW to hide console
                    subprocess.Popen([
                        scrcpy_path,
                        "-s", device_id,
                        "--window-title", f"FRT - Device Screen ({device_id})",
                        "--window-width", "500",
                        "--window-height", "1000",
                        "--always-on-top",
                        "--stay-awake"
                    ], 
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL)
                else:
                    subprocess.Popen([
                        scrcpy_path,
                        "-s", device_id,
                        "--window-title", f"FRT - Device Screen ({device_id})",
                        "--window-width", "500",
                        "--window-height", "1000",
                        "--always-on-top",
                        "--stay-awake"
                    ])
                
                self.add_activity(f"✓ Screen view opened for device {device_id}")
                
            except Exception as e:
                self.add_activity(f"✗ Failed to open screen view for {device_id}: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to open screen view:\n{str(e)}")
    

    def _go_home_screen(self):
        """Send device to home screen."""
        devices = self._get_devices_from_selection()
        if not devices:
            QMessageBox.warning(self, "No Selection", "Please select accounts with assigned devices.")
            return

        adb = self.adb_path

        def _run():
            from concurrent.futures import ThreadPoolExecutor
            def _home(device_id):
                try:
                    result = subprocess.run([adb, "-s", device_id, "shell", "input keyevent 3"],
                        capture_output=True, timeout=5)
                    if result.returncode == 0:
                        self.add_activity(f"✓ {device_id} → home screen")
                    else:
                        self.add_activity(f"✗ {device_id}: {result.stderr.strip()}")
                except Exception as e:
                    self.add_activity(f"✗ {device_id}: {e}")

            self.add_activity(f"Sending {len(devices)} device(s) to home screen...")
            with ThreadPoolExecutor(max_workers=len(devices)) as ex:
                list(ex.map(_home, devices))

        threading.Thread(target=_run, daemon=True).start()


    def _clear_recents(self):
        """Clear recently opened apps on selected devices."""
        devices = self._get_devices_from_selection()
        if not devices:
            QMessageBox.warning(self, "No Selection", "Please select accounts with assigned devices.")
            return

        adb = self.adb_path

        def _run():
            from concurrent.futures import ThreadPoolExecutor as _TPE
            import re as _re
            def _clear(device_id):
                try:
                    # Open recents screen and wait for it to fully load
                    subprocess.run([adb, "-s", device_id, "shell", "input keyevent KEYCODE_APP_SWITCH"],
                        capture_output=True, timeout=5)
                    time.sleep(2.5)

                    # Dump UI
                    subprocess.run([adb, "-s", device_id, "shell", "uiautomator dump /sdcard/ui_rec.xml"],
                        capture_output=True, timeout=8)
                    r = subprocess.run([adb, "-s", device_id, "shell", "cat /sdcard/ui_rec.xml"],
                        capture_output=True, text=True, timeout=5)
                    xml = r.stdout or ""

                    # Try "Close all" / "Clear all" button first
                    m = _re.search(r'text="([^"]*(?:close all|clear all|end all|dismiss all)[^"]*)"',
                                   xml, _re.IGNORECASE)
                    if m:
                        node_start = xml.rfind('<node', 0, m.start())
                        node_end = xml.find('/>', m.start())
                        node_str = xml[node_start:node_end+2] if node_start != -1 else ""
                        bm = _re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node_str)
                        if bm:
                            x1,y1,x2,y2 = map(int, bm.groups())
                            subprocess.run([adb, "-s", device_id, "shell",
                                f"input tap {(x1+x2)//2} {(y1+y2)//2}"],
                                capture_output=True, timeout=3)
                            time.sleep(1.5)

                    # Fallback: swipe cards up until XML stops changing
                    else:
                        prev_xml = xml
                        swiped = 0
                        for _ in range(20):
                            subprocess.run([adb, "-s", device_id, "shell",
                                "input swipe 540 800 540 100 250"],
                                capture_output=True, timeout=3)
                            time.sleep(0.5)
                            subprocess.run([adb, "-s", device_id, "shell",
                                "uiautomator dump /sdcard/ui_rec2.xml"],
                                capture_output=True, timeout=6)
                            r2 = subprocess.run([adb, "-s", device_id, "shell",
                                "cat /sdcard/ui_rec2.xml"],
                                capture_output=True, text=True, timeout=5)
                            xml2 = r2.stdout or ""
                            if xml2 == prev_xml:
                                break
                            prev_xml = xml2
                            swiped += 1

                    # Always go home — press twice to ensure recents is dismissed
                    subprocess.run([adb, "-s", device_id, "shell", "input keyevent KEYCODE_HOME"],
                        capture_output=True, timeout=3)
                    time.sleep(0.5)
                    subprocess.run([adb, "-s", device_id, "shell", "input keyevent KEYCODE_HOME"],
                        capture_output=True, timeout=3)
                    self.add_activity(f"✓ {device_id}: recents cleared")
                except Exception as e:
                    self.add_activity(f"✗ {device_id}: {e}")

            self.add_activity(f"Clearing recents on {len(devices)} device(s)...")
            with _TPE(max_workers=len(devices)) as ex:
                list(ex.map(_clear, devices))

        threading.Thread(target=_run, daemon=True).start()


    def _switch_keyboard(self):
        """Switch between phone keyboard and hardware keyboard."""
        devices = self._get_devices_from_selection()
        if not devices:
            QMessageBox.warning(self, "No Selection", "Please select accounts with assigned devices.")
            return
        
        device_id = devices[0]  # Use first device
        adb = self.adb_path
        
        # Show dialog to choose keyboard type
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_switch_keyboard"))
        dialog.setFixedSize(500, 280)
        dialog.setStyleSheet("""
            QDialog { 
                background: #1e1e1e; 
            }
            QLabel { 
                color: #cccccc; 
                font-size: 13px; 
                background: transparent;
            }
            QPushButton { 
                background: #252526;
                color: #cccccc;
                border: 2px solid #3d3d3d;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
                padding: 20px;
                text-align: left;
            }
            QPushButton:hover { 
                background: #2d2d2d;
                border-color: #4CAF50;
                color: #ffffff;
            }
            QPushButton:pressed {
                background: #4CAF50;
                border-color: #4CAF50;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title with icon
        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.keyboard', color='#4CAF50').pixmap(24, 24))
        title_row.addWidget(title_icon)
        
        label = QLabel("Choose keyboard input method")
        label.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold; background: transparent;")
        title_row.addWidget(label)
        title_row.addStretch()
        layout.addLayout(title_row)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #3d3d3d; border: none; max-height: 1px;")
        layout.addWidget(sep)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        # Phone keyboard button
        phone_btn = QPushButton()
        phone_btn.setFixedHeight(100)
        phone_icon = qta.icon('fa5s.mobile-alt', color='#4CAF50')
        phone_btn.setIcon(phone_icon)
        phone_btn.setIconSize(QSize(32, 32))
        phone_btn.setText("  Phone Keyboard\n  Use on-screen keyboard")
        phone_btn.setStyleSheet("""
            QPushButton {
                background: #252526;
                color: #cccccc;
                border: 2px solid #3d3d3d;
                border-radius: 6px;
                font-size: 13px;
                padding: 15px;
                text-align: center;
            }
            QPushButton:hover {
                background: #2d2d2d;
                border-color: #4CAF50;
                color: #ffffff;
            }
            QPushButton:pressed {
                background: #4CAF50;
                border-color: #4CAF50;
            }
        """)
        phone_btn.clicked.connect(lambda: self._set_keyboard_mode(device_id, adb, "phone", dialog))
        btn_layout.addWidget(phone_btn)
        
        # Hardware keyboard button
        hardware_btn = QPushButton()
        hardware_btn.setFixedHeight(100)
        hardware_icon = qta.icon('fa5s.keyboard', color='#4CAF50')
        hardware_btn.setIcon(hardware_icon)
        hardware_btn.setIconSize(QSize(32, 32))
        hardware_btn.setText("  Hardware Keyboard\n  Use PC keyboard")
        hardware_btn.setStyleSheet("""
            QPushButton {
                background: #252526;
                color: #cccccc;
                border: 2px solid #3d3d3d;
                border-radius: 6px;
                font-size: 13px;
                padding: 15px;
                text-align: center;
            }
            QPushButton:hover {
                background: #2d2d2d;
                border-color: #4CAF50;
                color: #ffffff;
            }
            QPushButton:pressed {
                background: #4CAF50;
                border-color: #4CAF50;
            }
        """)
        hardware_btn.clicked.connect(lambda: self._set_keyboard_mode(device_id, adb, "hardware", dialog))
        btn_layout.addWidget(hardware_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()
    

    def _set_keyboard_mode(self, device_id, adb, mode, dialog):
        """Set keyboard input mode."""
        try:
            if mode == "phone":
                # Show phone keyboard (enable soft keyboard)
                self.add_activity("Enabling phone keyboard...")
                
                # Enable soft keyboard to always show
                safe_subprocess_run([adb, "-s", device_id, "shell",
                    "settings put secure show_ime_with_hard_keyboard 1"],
                    capture_output=True)
                
                # Force show keyboard using IME command
                safe_subprocess_run([adb, "-s", device_id, "shell",
                    "am broadcast -a android.intent.action.CLOSE_SYSTEM_DIALOGS"],
                    capture_output=True)
                
                import time
                time.sleep(0.3)
                
                # Open messaging app or any app with text input
                safe_subprocess_run([adb, "-s", device_id, "shell",
                    "am start -n com.android.mms/.ui.ConversationList"],
                    capture_output=True)
                
                time.sleep(1)
                
                # Tap on compose button (usually at bottom right)
                safe_subprocess_run([adb, "-s", device_id, "shell",
                    "input tap 900 1700"],
                    capture_output=True)
                
                time.sleep(0.5)
                
                # Tap on message field
                safe_subprocess_run([adb, "-s", device_id, "shell",
                    "input tap 540 1700"],
                    capture_output=True)
                
                time.sleep(0.5)
                
                # Force show IME
                safe_subprocess_run([adb, "-s", device_id, "shell",
                    "ime enable com.android.inputmethod.latin/.LatinIME"],
                    capture_output=True)
                
                safe_subprocess_run([adb, "-s", device_id, "shell",
                    "ime set com.android.inputmethod.latin/.LatinIME"],
                    capture_output=True)
                
                self.add_activity("✓ Phone keyboard enabled - Keyboard should be visible now")
                
            else:  # hardware
                # Use hardware keyboard (hide soft keyboard)
                self.add_activity("Enabling hardware keyboard (PC keyboard)...")
                
                # Disable soft keyboard when hardware keyboard is connected
                safe_subprocess_run([adb, "-s", device_id, "shell",
                    "settings put secure show_ime_with_hard_keyboard 0"],
                    capture_output=True)
                
                # Hide keyboard
                safe_subprocess_run([adb, "-s", device_id, "shell",
                    "input keyevent 4"],  # KEYCODE_BACK to hide keyboard
                    capture_output=True)
                
                # Go to home
                safe_subprocess_run([adb, "-s", device_id, "shell",
                    "input keyevent 3"],
                    capture_output=True)
                
                self.add_activity("✓ Hardware keyboard enabled - Use PC keyboard in scrcpy")
            
            dialog.accept()
            
        except Exception as e:
            self.add_activity(f"✗ Failed to switch keyboard: {str(e)}")
            QMessageBox.critical(dialog, "Error", f"Failed to switch keyboard:\n{str(e)}")
    

    def _set_devices_working(self):
        """Configure device with optimal settings for working."""
        import threading
        
        devices = self._get_devices_from_selection()
        if not devices:
            QMessageBox.warning(self, "No Selection", "Please select accounts with assigned devices.")
            return
        
        adb = self.adb_path
        
        self.add_activity(f"Configuring {len(devices)} device(s) for optimal working...")
        
        def _run():
            for device_id in devices:
                try:
                    self.add_activity(f"→ Configuring device {device_id}...")
                    
                    # 1. Keep screen awake
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "settings put global stay_on_while_plugged_in 7"],
                        capture_output=True)
                    
                    # 2. Disable screen timeout
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "settings put system screen_off_timeout 2147483647"],
                        capture_output=True)
                    
                    # 3. Set brightness to medium
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "settings put system screen_brightness 128"],
                        capture_output=True)
                    
                    # 4. Disable animations for faster performance
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "settings put global window_animation_scale 0"],
                        capture_output=True)
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "settings put global transition_animation_scale 0"],
                        capture_output=True)
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "settings put global animator_duration_scale 0"],
                        capture_output=True)
                    
                    # 5. Enable USB debugging notification
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "settings put global adb_enabled 1"],
                        capture_output=True)
                    
                    # 6. Disable auto-rotate
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "settings put system accelerometer_rotation 0"],
                        capture_output=True)
                    
                    # 7. Set portrait orientation
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "settings put system user_rotation 0"],
                        capture_output=True)
                    
                    # 8. Disable notification sounds
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "settings put system notification_sound null"],
                        capture_output=True)
                    
                    # 9. Grant storage permissions to common apps
                    for pkg in ["com.android.chrome", "com.facebook.katana", "com.facebook.lite"]:
                        safe_subprocess_run([adb, "-s", device_id, "shell",
                            f"pm grant {pkg} android.permission.READ_EXTERNAL_STORAGE"],
                            capture_output=True)
                        safe_subprocess_run([adb, "-s", device_id, "shell",
                            f"pm grant {pkg} android.permission.WRITE_EXTERNAL_STORAGE"],
                            capture_output=True)
                    
                    # 10. Clear recent apps
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "am kill-all"],
                        capture_output=True)
                    
                    # 11. Go to home screen
                    safe_subprocess_run([adb, "-s", device_id, "shell",
                        "input keyevent 3"],
                        capture_output=True)
                    
                    self.add_activity(f"✓ Device {device_id} configured successfully!")
                    
                except Exception as e:
                    self.add_activity(f"✗ Failed to configure {device_id}: {str(e)}")
        
        threading.Thread(target=_run, daemon=True).start()
    

    def _open_vpn_app(self):
        """Open OpenVPN app on device."""
        import threading
        devices = self._get_devices_from_selection()
        if not devices:
            QMessageBox.warning(self, "No Selection", "Please select accounts with assigned devices.")
            return

        def _run():
            adb = self.adb_path
            success, failed = [], []
            for device_id in devices:
                self.add_activity(f"Opening OpenVPN app on {device_id}...")
                try:
                    result = subprocess.run([adb, "-s", device_id, "shell",
                        "am start -n de.blinkt.openvpn/.activities.MainActivity"],
                        capture_output=True, timeout=5)
                    if result.returncode == 0:
                        self.add_activity(f"✓ OpenVPN app opened on {device_id}")
                        success.append(device_id)
                    else:
                        self.add_activity(f"✗ Failed for {device_id} - Is it installed?")
                        failed.append(device_id)
                except Exception as e:
                    self.add_activity(f"✗ Failed for {device_id}: {str(e)}")
                    failed.append(device_id)

            msg = f"OpenVPN opened on {len(success)} device(s)."
            if failed:
                msg += f"\nFailed: {', '.join(failed)}"
            self._show_dialog_signal.emit("Done", msg)

        threading.Thread(target=_run, daemon=True).start()
    

    def _check_ip(self):
        """Check device's current IP address with country flag."""
        import threading
        
        devices = self._get_devices_from_selection()
        if not devices:
            QMessageBox.warning(self, "No Selection", "Please select accounts with assigned devices.")
            return
        
        device_id = devices[0]  # Use first device from selection
        adb = self.adb_path
        
        self.add_activity(f"Checking IP address for device {device_id}...")
        
        def _run():
            try:
                # Check local IP
                result = safe_subprocess_run([adb, "-s", device_id, "shell",
                    "ip addr show wlan0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1"],
                    capture_output=True)
                
                local_ip = result.stdout.strip() if result.stdout else "Unknown"
                
                # Check public IP and location via ipapi.co
                result2 = safe_subprocess_run([adb, "-s", device_id, "shell",
                    "curl -s 'https://ipapi.co/json/'"],
                    capture_output=True, timeout=15)
                
                import json
                ip_data = {}
                public_ip = "Unknown"
                country = "Unknown"
                country_code = "XX"
                city = "Unknown"
                region = "Unknown"
                isp = "Unknown"
                
                if result2.stdout:
                    try:
                        ip_data = json.loads(result2.stdout)
                        public_ip = ip_data.get('ip', 'Unknown')
                        country = ip_data.get('country_name', 'Unknown')
                        country_code = ip_data.get('country_code', 'XX')
                        city = ip_data.get('city', 'Unknown')
                        region = ip_data.get('region', 'Unknown')
                        isp = ip_data.get('org', 'Unknown')
                    except:
                        # Fallback to simple IP check
                        result3 = safe_subprocess_run([adb, "-s", device_id, "shell",
                            "curl -s ifconfig.me"],
                            capture_output=True, timeout=10)
                        public_ip = result3.stdout.strip() if result3.stdout else "Unknown"
                
                # Emit signal to show dialog on main thread (don't call add_activity from thread)
                self._ip_check_signal.emit(local_ip, public_ip, country, country_code, city, region, isp, device_id)
                
            except Exception as e:
                # Don't call add_activity from thread - just emit error signal
                self._ip_check_signal.emit("Error", "Error", "Error", "XX", str(e), "", "", device_id)
        
        threading.Thread(target=_run, daemon=True).start()
    

    def _show_ip_dialog(self, local_ip, public_ip, country, country_code, city, region, isp, device_id):
        """Show IP information dialog with country flag."""
        # Log to activity (now safe because we're on main thread)
        if local_ip != "Error":
            self.add_activity(f"📱 Local IP: {local_ip}")
            self.add_activity(f"🌐 Public IP: {public_ip}")
            self.add_activity(f"🌍 Location: {city}, {country}")
        else:
            self.add_activity(f"✗ Failed to check IP: {city}")  # city contains error message
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_ip_info"))
        dialog.setFixedSize(450, 380)
        dialog.setStyleSheet("""
            QDialog { background: #1e1e1e; }
            QLabel { color: #cccccc; font-size: 13px; background: transparent; }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel("IP Address Information")
        title.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #3d3d3d; border: none; max-height: 1px;")
        layout.addWidget(sep)
        
        # Country with icon and flag
        country_row = QHBoxLayout()
        country_row.setSpacing(10)
        country_row.addStretch()
        
        # Globe icon
        globe_icon = QLabel()
        globe_icon.setPixmap(qta.icon('fa5s.globe-americas', color='#4CAF50').pixmap(32, 32))
        country_row.addWidget(globe_icon)
        
        # Country code badge
        code_badge = QLabel(country_code)
        code_badge.setFixedSize(50, 32)
        code_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        code_badge.setStyleSheet("""
            background: #4CAF50;
            color: #ffffff;
            font-size: 16px;
            font-weight: bold;
            border-radius: 4px;
        """)
        country_row.addWidget(code_badge)
        
        # Country name
        country_label = QLabel(country)
        country_label.setStyleSheet("color: #4CAF50; font-size: 20px; font-weight: bold; background: transparent;")
        country_row.addWidget(country_label)
        
        country_row.addStretch()
        layout.addLayout(country_row)
        
        # Location
        location_label = QLabel(f"{city}, {region}")
        location_label.setStyleSheet("color: #888888; font-size: 13px; background: transparent;")
        location_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(location_label)
        
        layout.addSpacing(10)
        
        # IP Information in simple rows
        def add_info_row(label_text, value_text, value_color='#4CAF50'):
            row = QHBoxLayout()
            row.setSpacing(10)
            
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #888888; font-size: 13px; min-width: 100px;")
            row.addWidget(lbl)
            
            val = QLabel(value_text)
            val.setStyleSheet(f"color: {value_color}; font-size: 13px; font-weight: 600;")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(val, 1)
            
            layout.addLayout(row)
        
        add_info_row("Local IP:", local_ip, '#4CAF50')
        add_info_row("Public IP:", public_ip, '#2196F3')
        add_info_row("ISP:", isp, '#FF9800')
        add_info_row("Device:", device_id, '#888888')
        
        layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(40)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: #fff;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #45a049; }
        """)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
    

    def _get_flag_emoji(self, country_code):
        """Convert country code to flag emoji."""
        if not country_code or len(country_code) != 2:
            return "🌍"
        
        # Convert country code to flag emoji
        # Each letter is converted to regional indicator symbol
        flag = ""
        for char in country_code.upper():
            flag += chr(ord(char) + 127397)
        return flag
    

    def _connect_random_proxy(self):
        """Connect each selected device to a random OpenVPN profile."""
        import threading, random, time, os as _os, re as _re
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt

        devices = self._get_devices_from_selection()
        if not devices:
            QMessageBox.warning(self, "No Selection", "Please select accounts with assigned devices.")
            return

        vpn_dir = _os.path.join(_PROJECT_ROOT, "vpn")
        if not _os.path.exists(vpn_dir):
            QMessageBox.warning(self, "VPN", "VPN folder not found."); return
        
        # Show loading dialog while scanning VPN files
        scan_progress = QProgressDialog("Scanning VPN files...", None, 0, 0, self)
        scan_progress.setWindowTitle("Loading")
        scan_progress.setWindowModality(Qt.WindowModality.WindowModal)
        scan_progress.setMinimumDuration(0)
        scan_progress.setValue(0)
        scan_progress.setStyleSheet("""
            QProgressDialog {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
            }
            QProgressDialog QLabel {
                color: #cccccc;
                font-size: 13px;
                padding: 10px;
            }
            QProgressBar {
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                background: #252525;
                text-align: center;
                color: #cccccc;
            }
            QProgressBar::chunk {
                background: #4CAF50;
                border-radius: 3px;
            }
        """)
        scan_progress.show()
        QApplication.processEvents()
        
        # Scan VPN files in background thread
        ovpn_files = []
        def _scan():
            nonlocal ovpn_files
            try:
                ovpn_files = sorted([f for f in _os.listdir(vpn_dir) if f.endswith(".ovpn")])
            except Exception as e:
                print(f"Error scanning VPN files: {e}")
        
        scan_thread = threading.Thread(target=_scan, daemon=True)
        scan_thread.start()
        scan_thread.join(timeout=5)
        
        scan_progress.close()
        
        if not ovpn_files:
            QMessageBox.warning(self, "VPN", "No .ovpn files found in vpn/ folder."); return

        # ── Credentials dialog ────────────────────────────────────────────
        import tempfile
        vpn_creds_file = _os.path.join(tempfile.gettempdir(), "frt_vpn_creds.json")
        saved_creds = {}
        if _os.path.exists(vpn_creds_file):
            try:
                with open(vpn_creds_file, 'r', encoding='utf-8') as _f:
                    saved_creds = json.load(_f)
            except Exception:
                pass

        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_connect_random"))
        dialog.setFixedSize(400, 220)
        dialog.setStyleSheet("""
            QDialog { background: #1e1e1e; }
            QLabel { color: #cccccc; font-size: 12px; background: transparent; }
            QLineEdit { background: #252526; border: 1px solid #3d3d3d; border-radius: 4px;
                        padding: 0 10px; color: #cccccc; font-size: 12px; height: 36px; }
            QLineEdit:focus { border-color: #4CAF50; }
            QPushButton { background: #4CAF50; color: #fff; border: none; border-radius: 4px;
                          font-size: 13px; font-weight: 600; padding: 8px 20px; }
            QPushButton:hover { background: #45a049; }
        """)
        lay = QVBoxLayout(dialog); lay.setContentsMargins(24, 20, 24, 20); lay.setSpacing(10)
        lay.addWidget(QLabel(f"Random profile per device  ({len(devices)} device(s))"))

        user_input = QLineEdit(); user_input.setPlaceholderText("VPN Username")
        user_input.setText(saved_creds.get('username', ''))
        lay.addWidget(user_input)

        pass_input = QLineEdit(); pass_input.setPlaceholderText("VPN Password")
        pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        pass_input.setText(saved_creds.get('password', ''))
        lay.addWidget(pass_input)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel"); cancel_btn.setStyleSheet(
            "QPushButton { background: #3d3d3d; color: #ccc; border: none; border-radius: 4px; padding: 8px 20px; }"
            "QPushButton:hover { background: #555; }")
        cancel_btn.clicked.connect(dialog.reject)
        connect_btn = QPushButton("Connect"); connect_btn.clicked.connect(dialog.accept)
        connect_btn.setDefault(False); connect_btn.setAutoDefault(False)
        cancel_btn.setDefault(False); cancel_btn.setAutoDefault(False)
        btn_row.addWidget(cancel_btn); btn_row.addWidget(connect_btn)
        lay.addLayout(btn_row)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        username = user_input.text().strip()
        password = pass_input.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "Missing Credentials", "Please enter both username and password.")
            return

        # Save credentials
        try:
            with open(vpn_creds_file, 'w', encoding='utf-8') as _f:
                json.dump({'username': username, 'password': password}, _f)
        except Exception:
            pass

        adb = self.adb_path

        # Check which profiles are already imported on each device, then assign randomly from those
        import re as _re

        def _get_imported_profiles(dev):
            try:
                r = subprocess.run([adb, "-s", dev, "shell",
                    "cat /data/user/0/de.blinkt.openvpn/shared_prefs/VPN.xml 2>/dev/null"],
                    capture_output=True, text=True, timeout=8)
                return set(_re.findall(r'<string name="mName">([^<]+)</string>', r.stdout or ""))
            except Exception:
                return set()

        def _file_to_label(fname):
            n = fname.replace(".ovpn", "")
            if n.startswith("NCVPN-"): n = n[6:]
            if n.endswith("-TCP"): n = n[:-4]
            elif n.endswith("-UDP"): n = n[:-4]
            d = n.index("-") if "-" in n else -1
            return f"{n[:d]} - {n[d+1:]}" if d > 0 else n

        def _file_to_raw(fname):
            """Return the raw profile name as stored in OpenVPN (filename without .ovpn)."""
            return fname.replace(".ovpn", "")

        self.add_activity("Checking imported profiles on each device...")
        from concurrent.futures import ThreadPoolExecutor as _TPE
        with _TPE(max_workers=len(devices)) as ex:
            imported_map = dict(zip(devices, ex.map(_get_imported_profiles, devices)))

        assignments = {}
        to_import = {}  # dev -> file to import first
        for dev in devices:
            available = [f for f in ovpn_files if _file_to_raw(f) in imported_map[dev]]
            if not available:
                # Pick a random file to import then connect
                chosen = random.choice(ovpn_files)
                to_import[dev] = chosen
                assignments[dev] = chosen
                self.add_activity(f"  {dev}: no profiles — will import {_file_to_label(chosen)} first")
            else:
                assignments[dev] = random.choice(available)
                self.add_activity(f"  {dev} → {_file_to_label(assignments[dev])}")

        if not assignments:
            QMessageBox.warning(self, "No Profiles",
                "No imported VPN profiles found on any device.\nUse 'Import Selected Files' first.")
            return

        def _connect_device(dev, profile_file):
            try:
                raw_name = profile_file.replace(".ovpn", "")
                name = raw_name
                if name.startswith("NCVPN-"): name = name[6:]
                if name.endswith("-TCP"): name = name[:-4]
                elif name.endswith("-UDP"): name = name[:-4]
                dash = name.index("-") if "-" in name else -1
                label = f"{name[:dash]} - {name[dash+1:]}" if dash > 0 else name

                # ── Auto-import if needed ──────────────────────────────
                if dev in to_import:
                    self.add_activity(f"→ {dev}: importing {raw_name}...")
                    fp = _os.path.join(vpn_dir, profile_file)
                    dest = f"/data/local/tmp/vpn/{profile_file}"
                    subprocess.run([adb, "-s", dev, "shell", "mkdir -p /data/local/tmp/vpn"],
                        capture_output=True, timeout=5)
                    subprocess.run([adb, "-s", dev, "push", fp, dest],
                        capture_output=True, timeout=20)
                    subprocess.run([adb, "-s", dev, "shell", f"chmod 644 {dest}"],
                        capture_output=True, timeout=5)
                    subprocess.run([adb, "-s", dev, "shell",
                        f'am start -n de.blinkt.openvpn/.activities.ConfigConverter '
                        f'-a android.intent.action.VIEW '
                        f'-d "file://{dest}" '
                        f'-t application/x-openvpn-profile'],
                        capture_output=True, timeout=5)
                    # Wait for ConfigConverter and tap save
                    import_xml = ""
                    for _ in range(6):
                        time.sleep(1)
                        try:
                            subprocess.run([adb, "-s", dev, "shell", "uiautomator dump /sdcard/ui_imp.xml"],
                                capture_output=True, timeout=8)
                            r = subprocess.run([adb, "-s", dev, "shell", "cat /sdcard/ui_imp.xml"],
                                capture_output=True, text=True, timeout=5)
                            import_xml = r.stdout or ""
                            if "EditText" in import_xml or "Convert Config" in import_xml:
                                break
                        except Exception:
                            pass
                    m_btn = _re.search(
                        r'class="android\.widget\.ImageButton"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                        import_xml)
                    if m_btn:
                        x1,y1,x2,y2 = map(int, m_btn.groups())
                        subprocess.run([adb, "-s", dev, "shell",
                            f"input tap {(x1+x2)//2} {(y1+y2)//2}"],
                            capture_output=True, timeout=3)
                    else:
                        subprocess.run([adb, "-s", dev, "shell", "input tap 987 1726"],
                            capture_output=True, timeout=3)
                    time.sleep(3)  # wait for save to complete
                    # Press BACK to return to MainActivity
                    subprocess.run([adb, "-s", dev, "shell", "input keyevent KEYCODE_BACK"],
                        capture_output=True, timeout=3)
                    time.sleep(2)
                    # Press BACK once more in case we're still in ConfigConverter
                    subprocess.run([adb, "-s", dev, "shell", "input keyevent KEYCODE_BACK"],
                        capture_output=True, timeout=3)
                    time.sleep(1)
                    self.add_activity(f"  ✓ imported {raw_name} on {dev}")

                self.add_activity(f"→ {dev}: connecting to {label}...")

                # ── Helpers ────────────────────────────────────────────
                def _uidump(filename, timeout=10, retries=2):
                    for _ in range(retries):
                        try:
                            subprocess.run([adb, "-s", dev, "shell",
                                f"uiautomator dump {filename}"],
                                capture_output=True, timeout=timeout)
                            return True
                        except subprocess.TimeoutExpired:
                            time.sleep(1)
                    return False

                def _type_into_field(tx, ty, text):
                    subprocess.run([adb,"-s",dev,"shell",f"input tap {tx} {ty}"], capture_output=True, timeout=3)
                    time.sleep(0.4)
                    # Select all then delete — use CTRL+A then DEL (more reliable than longpress)
                    subprocess.run([adb,"-s",dev,"shell","input keyevent KEYCODE_CTRL_A"], capture_output=True, timeout=3)
                    time.sleep(0.2)
                    subprocess.run([adb,"-s",dev,"shell","input keyevent KEYCODE_DEL"], capture_output=True, timeout=3)
                    time.sleep(0.2)
                    # Extra DEL pass in case one char remains
                    subprocess.run([adb,"-s",dev,"shell","input keyevent KEYCODE_DEL"], capture_output=True, timeout=3)
                    time.sleep(0.2)
                    safe = text.replace(" ", "%s").replace("'", "\\'")
                    subprocess.run([adb,"-s",dev,"shell",f"input text '{safe}'"], capture_output=True, timeout=5)
                    time.sleep(0.3)

                def _fill_need_password(xml_text):
                    if "Need Password" not in xml_text and "Password" not in xml_text:
                        return False
                    et_matches = list(_re.finditer(
                        r'class="android\.widget\.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                        xml_text))
                    if len(et_matches) >= 2:
                        x1,y1,x2,y2 = map(int, et_matches[0].groups())
                        _type_into_field((x1+x2)//2, (y1+y2)//2, username)
                        # Dismiss keyboard before filling second field
                        subprocess.run([adb,"-s",dev,"shell","input keyevent KEYCODE_BACK"], capture_output=True, timeout=3)
                        time.sleep(0.5)
                        x1,y1,x2,y2 = map(int, et_matches[1].groups())
                        _type_into_field((x1+x2)//2, (y1+y2)//2, password)
                    elif len(et_matches) == 1:
                        x1,y1,x2,y2 = map(int, et_matches[0].groups())
                        _type_into_field((x1+x2)//2, (y1+y2)//2, password)
                    # Re-dump to get fresh coords after keyboard may shift layout
                    _uidump("/sdcard/ui_ok2.xml")
                    time.sleep(0.5)
                    ui_ok2 = subprocess.run([adb,"-s",dev,"shell","cat /sdcard/ui_ok2.xml"],
                        capture_output=True, text=True, timeout=5)
                    ok_xml = ui_ok2.stdout if ui_ok2.stdout else xml_text
                    # Tap "Save Password" checkbox if present
                    save_m = _re.search(r'text="Save Password"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', ok_xml)
                    if save_m:
                        x1,y1,x2,y2 = map(int, save_m.groups())
                        subprocess.run([adb,"-s",dev,"shell",f"input tap {(x1+x2)//2} {(y1+y2)//2}"],
                            capture_output=True, timeout=3)
                        time.sleep(0.3)
                    ok_m = _re.search(r'text="OK"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', ok_xml)
                    if ok_m:
                        x1,y1,x2,y2 = map(int, ok_m.groups())
                        subprocess.run([adb,"-s",dev,"shell",f"input tap {(x1+x2)//2} {(y1+y2)//2}"],
                            capture_output=True, timeout=3)
                        time.sleep(3)
                    else:
                        subprocess.run([adb,"-s",dev,"shell","input keyevent KEYCODE_ENTER"],
                            capture_output=True, timeout=3)
                        time.sleep(3)
                    return True

                # ── Open OpenVPN MainActivity ──────────────────────────
                subprocess.run([adb, "-s", dev, "shell",
                    "am start -n de.blinkt.openvpn/.activities.MainActivity"],
                    capture_output=True, timeout=5)
                # Wait until OpenVPN is actually in foreground (not launcher)
                for _ in range(10):
                    time.sleep(1)
                    chk = subprocess.run([adb,"-s",dev,"shell",
                        "dumpsys activity activities | grep mResumedActivity"],
                        capture_output=True, text=True, timeout=5)
                    if "de.blinkt.openvpn" in (chk.stdout or ""):
                        break

                ovpn_base = raw_name  # e.g. NCVPN-AU-Adelaide-TCP

                # Disconnect any existing VPN before connecting to new profile
                tun_pre = subprocess.run([adb,"-s",dev,"shell","ip addr show tun0"],
                    capture_output=True, text=True, timeout=5)
                if tun_pre.stdout and "inet" in tun_pre.stdout:
                    self.add_activity(f"  Disconnecting existing VPN on {dev}...")
                    subprocess.run([adb,"-s",dev,"shell",
                        "am start -n de.blinkt.openvpn/.activities.DisconnectVPN"],
                        capture_output=True, timeout=5)
                    time.sleep(2)
                    # Confirm disconnect dialog if it appears
                    _uidump("/sdcard/ui_disc.xml")
                    ui_disc = subprocess.run([adb,"-s",dev,"shell","cat /sdcard/ui_disc.xml"],
                        capture_output=True, text=True, timeout=5)
                    disc_xml = ui_disc.stdout or ""
                    for btn_text in ["Yes", "OK", "Disconnect"]:
                        dm = _re.search(
                            rf'text="{btn_text}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', disc_xml)
                        if dm:
                            x1,y1,x2,y2 = map(int, dm.groups())
                            subprocess.run([adb,"-s",dev,"shell",f"input tap {(x1+x2)//2} {(y1+y2)//2}"],
                                capture_output=True, timeout=3)
                            time.sleep(2)
                            break
                    # Re-open MainActivity after disconnect
                    subprocess.run([adb,"-s",dev,"shell",
                        "am start -n de.blinkt.openvpn/.activities.MainActivity"],
                        capture_output=True, timeout=5)
                    for _ in range(10):
                        time.sleep(1)
                        chk = subprocess.run([adb,"-s",dev,"shell",
                            "dumpsys activity activities | grep mResumedActivity"],
                            capture_output=True, text=True, timeout=5)
                        if "de.blinkt.openvpn" in (chk.stdout or ""):
                            break

                # ── Navigate to PROFILES tab ───────────────────────────
                _uidump("/sdcard/ui_tabs_r.xml")
                time.sleep(1)
                ui_tabs = subprocess.run([adb,"-s",dev,"shell","cat /sdcard/ui_tabs_r.xml"],
                    capture_output=True, text=True, timeout=5)
                tabs_xml = ui_tabs.stdout if ui_tabs.stdout else ""

                # Handle Need Password if already showing
                _pwd_handled = False
                prof_xml = ""
                if _fill_need_password(tabs_xml):
                    _pwd_handled = True
                    self._update_proxy_in_cache(dev, f"VPN: {label}")

                if not _pwd_handled:
                    tab_m = _re.search(
                        r'text="PROFILES"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tabs_xml)
                    if tab_m:
                        x1,y1,x2,y2 = map(int, tab_m.groups())
                        subprocess.run([adb,"-s",dev,"shell",f"input tap {(x1+x2)//2} {(y1+y2)//2}"],
                            capture_output=True, timeout=3)
                        time.sleep(2)

                    # ── Find and tap the profile row ───────────────────
                    _uidump("/sdcard/ui_prof_r.xml")
                    time.sleep(1)
                    ui_prof = subprocess.run([adb,"-s",dev,"shell","cat /sdcard/ui_prof_r.xml"],
                        capture_output=True, text=True, timeout=5)
                    prof_xml = ui_prof.stdout if ui_prof.stdout else ""

                    if _fill_need_password(prof_xml):
                        _pwd_handled = True
                        self._update_proxy_in_cache(dev, f"VPN: {label}")

                if not _pwd_handled:
                    tap_x, tap_y = None, None
                    # Scroll to top first, then scan downward page by page
                    subprocess.run([adb,"-s",dev,"shell","input swipe 540 400 540 1600 300"],
                        capture_output=True, timeout=3)
                    time.sleep(0.8)
                    for _sp in range(15):
                        cur_xml = prof_xml if _sp == 0 else ""
                        if _sp > 0:
                            _uidump(f"/sdcard/ui_sp_{_sp}.xml")
                            time.sleep(0.8)
                            r_sp = subprocess.run([adb,"-s",dev,"shell",f"cat /sdcard/ui_sp_{_sp}.xml"],
                                capture_output=True, text=True, timeout=5)
                            cur_xml = r_sp.stdout or ""
                        for search_name in [ovpn_base, label, name]:
                            nm = _re.search(
                                rf'text="{_re.escape(search_name)}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                                cur_xml)
                            if nm:
                                x1,y1,x2,y2 = map(int, nm.groups())
                                tap_x,tap_y = (x1+x2)//2,(y1+y2)//2
                                break
                        if tap_x is not None:
                            break
                        # Scroll down one page
                        subprocess.run([adb,"-s",dev,"shell","input swipe 540 1400 540 600 400"],
                            capture_output=True, timeout=3)
                        time.sleep(0.8)

                    if tap_x is not None:
                        self.add_activity(f"  Tapping profile at ({tap_x},{tap_y}) on {dev}")
                        subprocess.run([adb,"-s",dev,"shell",f"input tap {tap_x} {tap_y}"],
                            capture_output=True, timeout=3)
                        time.sleep(2)
                        # Verify the password dialog is for the correct profile
                        _uidump("/sdcard/ui_verify.xml")
                        ui_verify = subprocess.run([adb,"-s",dev,"shell","cat /sdcard/ui_verify.xml"],
                            capture_output=True, text=True, timeout=5)
                        v_xml = ui_verify.stdout or ""
                        if "Need Password" in v_xml and ovpn_base not in v_xml:
                            # Wrong profile dialog — cancel and do a scrolling search
                            cancel_m = _re.search(r'text="CANCEL"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', v_xml)
                            if cancel_m:
                                x1,y1,x2,y2 = map(int, cancel_m.groups())
                                subprocess.run([adb,"-s",dev,"shell",f"input tap {(x1+x2)//2} {(y1+y2)//2}"],
                                    capture_output=True, timeout=3)
                                time.sleep(1)
                            # Scroll to top first, then scan downward
                            subprocess.run([adb,"-s",dev,"shell","input swipe 540 400 540 1600 300"],
                                capture_output=True, timeout=3)
                            time.sleep(1)
                            found_after_scroll = False
                            for _scroll_attempt in range(15):
                                _uidump(f"/sdcard/ui_scroll_{_scroll_attempt}.xml")
                                time.sleep(0.8)
                                ui_s = subprocess.run([adb,"-s",dev,"shell",
                                    f"cat /sdcard/ui_scroll_{_scroll_attempt}.xml"],
                                    capture_output=True, text=True, timeout=5)
                                s_xml = ui_s.stdout or ""
                                for search_name in [ovpn_base, label, name]:
                                    nm2 = _re.search(
                                        rf'text="{_re.escape(search_name)}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                                        s_xml)
                                    if nm2:
                                        x1,y1,x2,y2 = map(int, nm2.groups())
                                        self.add_activity(f"  Found after scroll at ({(x1+x2)//2},{(y1+y2)//2}) on {dev}")
                                        subprocess.run([adb,"-s",dev,"shell",
                                            f"input tap {(x1+x2)//2} {(y1+y2)//2}"],
                                            capture_output=True, timeout=3)
                                        time.sleep(2)
                                        found_after_scroll = True
                                        break
                                if found_after_scroll:
                                    break
                                # Scroll down one page
                                subprocess.run([adb,"-s",dev,"shell","input swipe 540 1400 540 600 400"],
                                    capture_output=True, timeout=3)
                                time.sleep(0.8)
                    else:
                        self.add_activity(f"  ⚠ Profile row not found on {dev}, using default tap")
                        subprocess.run([adb,"-s",dev,"shell","input tap 493 336"],
                            capture_output=True, timeout=3)
                        time.sleep(2)

                    # ── Wait for Need Password dialog ──────────────────
                    for _pi in range(5):
                        time.sleep(1)
                        _uidump("/sdcard/ui_pwd_r.xml")
                        ui_pwd = subprocess.run([adb,"-s",dev,"shell","cat /sdcard/ui_pwd_r.xml"],
                            capture_output=True, text=True, timeout=5)
                        if ui_pwd.stdout and _fill_need_password(ui_pwd.stdout):
                            _pwd_handled = True
                            self._update_proxy_in_cache(dev, f"VPN: {label}")
                            break

                    if not _pwd_handled:
                        tun_chk = subprocess.run([adb,"-s",dev,"shell","ip addr show tun0"],
                            capture_output=True, text=True, timeout=5)
                        if not (tun_chk.stdout and "inet" in tun_chk.stdout):
                            self.add_activity(f"  ⚠ Password dialog not detected on {dev}")

                # ── Poll tun0 for connection ───────────────────────────
                connected = False
                for _ in range(20):
                    tun = subprocess.run([adb,"-s",dev,"shell","ip addr show tun0"],
                        capture_output=True, text=True, timeout=5)
                    if tun.stdout and "inet" in tun.stdout:
                        connected = True
                        break
                    time.sleep(1)

                if connected:
                    self.add_activity(f"✓ {dev}: connected → {label}")
                    self._update_proxy_in_cache(dev, f"VPN: {label}")
                else:
                    self.add_activity(f"✗ {dev}: not connected after 20s")

            except Exception as e:
                self.add_activity(f"✗ {dev}: {e}")

        # Create custom non-modal progress dialog
        progress = VPNProgressDialog(
            "Connecting to VPN",
            f"Connecting {len(devices)} device(s) to random VPN...\nPlease wait...",
            len(devices),
            "green",
            self
        )
        progress.show()
        progress.raise_()
        progress.activateWindow()
        QApplication.processEvents()
        
        # Store reference
        self._current_vpn_progress = progress
        
        # Connect signal to update progress
        def update_progress_slot(value, text):
            if hasattr(self, '_current_vpn_progress') and self._current_vpn_progress:
                try:
                    self._current_vpn_progress.update_progress(value, text)
                except:
                    pass
        
        self._vpn_progress_signal.connect(update_progress_slot)
        
        completed = [0]

        def _run():
            import concurrent.futures
            
            def _connect_with_progress(dev, profile):
                try:
                    _connect_device(dev, profile)
                finally:
                    completed[0] += 1
                    # Update status text (progress bar is animated)
                    self._vpn_progress_signal.emit(
                        completed[0],
                        f"Connecting {len(devices)} device(s) to random VPN...\n"
                        f"Completed: {completed[0]}/{len(devices)} devices"
                    )
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(devices)) as ex:
                concurrent.futures.wait([
                    ex.submit(_connect_with_progress, dev, assignments[dev])
                    for dev in devices
                ])
            
            # Disconnect signal
            try:
                self._vpn_progress_signal.disconnect(update_progress_slot)
            except:
                pass
            
            # Close progress dialog via signal (thread-safe)
            self.add_activity("✓ Random VPN connect done")
            self._vpn_done_signal.emit(len(devices))

        # Connect done signal to close dialog
        def close_dialog_slot(count):
            if hasattr(self, '_current_vpn_progress') and self._current_vpn_progress:
                try:
                    self._current_vpn_progress.close()
                    self._current_vpn_progress = None
                except:
                    pass
        
        self._vpn_done_signal.connect(close_dialog_slot)

        threading.Thread(target=_run, daemon=True).start()
    

    def _connect_specific_proxy(self):
        """Connect devices to specific VPN location using OpenVPN with UI automation."""
        from PyQt6.QtWidgets import QApplication, QProgressDialog
        from PyQt6.QtCore import Qt
        
        # Check VPN folder FIRST before doing anything else
        vpn_dir = os.path.join(_PROJECT_ROOT, "vpn")
        if not os.path.exists(vpn_dir):
            QMessageBox.warning(self, "VPN Folder Not Found", 
                f"VPN folder not found at:\n{vpn_dir}\n\n"
                "Please create a 'vpn' folder with .ovpn files.")
            return
        
        # Show loading dialog while scanning VPN files
        progress = QProgressDialog("Scanning VPN files...", None, 0, 0, self)
        progress.setWindowTitle("Loading")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()
        
        # Read VPN files in background thread to avoid blocking UI
        vpn_files = []
        def _scan_vpn_files():
            nonlocal vpn_files
            try:
                vpn_files = [f for f in os.listdir(vpn_dir) if f.endswith(".ovpn")]
            except Exception as e:
                print(f"Error scanning VPN files: {e}")
        
        import threading
        scan_thread = threading.Thread(target=_scan_vpn_files, daemon=True)
        scan_thread.start()
        scan_thread.join(timeout=5)  # Wait max 5 seconds
        
        progress.close()
        
        if not vpn_files:
            QMessageBox.warning(self, "No VPN Files", 
                "No .ovpn files found in vpn/ folder.")
            return
        
        # Now check for devices
        devices = self._get_devices_from_selection()
        
        if not devices:
            QMessageBox.warning(self, "No Devices", 
                "No devices assigned to selected accounts.\n\nPlease click 'Load Devices' first, then select accounts.")
            return
        
        # Show dialog to select VPN location
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_connect_specific"))
        dialog.setFixedSize(450, 350)
        dialog.setStyleSheet("""
            QDialog { background: #1e1e1e; }
            QLabel { color: #cccccc; font-size: 13px; }
            QComboBox {
                background: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                color: #cccccc;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #cccccc;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background: #2d2d2d;
                border: 1px solid #3d3d3d;
                selection-background-color: rgba(76,175,80,0.3);
                color: #cccccc;
            }
            QLineEdit {
                background: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                color: #cccccc;
                font-size: 13px;
            }
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #45a049; }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Select VPN Location")
        title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        # Location dropdown
        location_label = QLabel("Choose VPN Location:")
        layout.addWidget(location_label)
        
        location_combo = SafeComboBox()
        
        # Parse VPN files and populate dropdown (same as VPN system)
        vpn_data = {}
        for f in sorted(vpn_files):
            # Format: NCVPN-US-Los Angeles-TCP.ovpn
            name = f.replace(".ovpn", "")
            if name.startswith("NCVPN-"):
                name = name[6:]
            if name.endswith("-TCP"):
                name = name[:-4]
            elif name.endswith("-UDP"):
                name = name[:-4]
            
            # Split on first dash to get country and city
            if "-" in name:
                idx = name.index("-")
                country = name[:idx]
                city = name[idx+1:]
                label = f"{country} - {city}"
            else:
                label = name
            
            vpn_data[label] = f
            location_combo.addItem(label)
        
        if location_combo.count() == 0:
            QMessageBox.warning(self, "No VPN Files", "No valid VPN files found.")
            return
        
        layout.addWidget(location_combo)
        
        # Load saved credentials from cache
        import tempfile
        vpn_creds_file = os.path.join(tempfile.gettempdir(), "frt_vpn_creds.json")
        saved_creds = {}
        if os.path.exists(vpn_creds_file):
            try:
                with open(vpn_creds_file, 'r', encoding='utf-8') as f:
                    saved_creds = json.load(f)
            except:
                pass
        
        # Username input
        username_label = QLabel("VPN Username:")
        layout.addWidget(username_label)
        
        username_input = QLineEdit()
        username_input.setPlaceholderText("Enter VPN username")
        username_input.setText(saved_creds.get('username', ''))
        layout.addWidget(username_input)
        
        # Password input
        password_label = QLabel("VPN Password:")
        layout.addWidget(password_label)
        
        password_input = QLineEdit()
        password_input.setPlaceholderText("Enter VPN password")
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_input.setText(saved_creds.get('password', ''))
        layout.addWidget(password_input)
        
        # Restore last selected location
        if saved_creds.get('location'):
            idx = location_combo.findText(saved_creds['location'])
            if idx >= 0:
                location_combo.setCurrentIndex(idx)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        connect_btn = QPushButton("Connect")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #555555;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
            }
            QPushButton:hover { background: #666666; }
        """)
        
        connect_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(connect_btn)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_location = location_combo.currentText()
            vpn_file = vpn_data.get(selected_location)
            username = username_input.text().strip()
            password = password_input.text().strip()
            
            if not username or not password:
                QMessageBox.warning(self, "Missing Credentials", "Please enter both username and password.")
                return
            
            if not vpn_file:
                QMessageBox.warning(self, "No VPN File", f"No VPN file found for {selected_location}")
                return
            
            # Save credentials for next time
            try:
                with open(vpn_creds_file, 'w', encoding='utf-8') as f:
                    json.dump({'username': username, 'password': password, 'location': selected_location}, f)
            except:
                pass
            
            self.add_activity(f"Connecting {len(devices)} device(s) to {selected_location} VPN...")
            
            # Get the full path to the VPN file
            vpn_folder = os.path.join(_PROJECT_ROOT, "vpn")
            vpn_file_full_path = os.path.join(vpn_folder, vpn_file)
            
            # Use the SAME working logic as Connect Random VPN
            import threading, time, re as _re
            
            def _connect_device(dev):
                """Connect a single device - using the WORKING logic from _connect_random_proxy"""
                try:
                    adb = self.adb_path
                    raw_name = vpn_file.replace(".ovpn", "")
                    
                    # Helper functions (same as working Random VPN)
                    def _uidump(filename, timeout=10, retries=2):
                        for _ in range(retries):
                            try:
                                subprocess.run([adb, "-s", dev, "shell", f"uiautomator dump {filename}"],
                                    capture_output=True, timeout=timeout)
                                return True
                            except subprocess.TimeoutExpired:
                                time.sleep(1)
                        return False

                    def _type_into_field(tx, ty, text):
                        subprocess.run([adb,"-s",dev,"shell",f"input tap {tx} {ty}"], capture_output=True, timeout=3)
                        time.sleep(0.4)
                        subprocess.run([adb,"-s",dev,"shell","input keyevent KEYCODE_CTRL_A"], capture_output=True, timeout=3)
                        time.sleep(0.2)
                        subprocess.run([adb,"-s",dev,"shell","input keyevent KEYCODE_DEL"], capture_output=True, timeout=3)
                        time.sleep(0.2)
                        subprocess.run([adb,"-s",dev,"shell","input keyevent KEYCODE_DEL"], capture_output=True, timeout=3)
                        time.sleep(0.2)
                        safe = text.replace(" ", "%s").replace("'", "\\'")
                        subprocess.run([adb,"-s",dev,"shell",f"input text '{safe}'"], capture_output=True, timeout=5)
                        time.sleep(0.3)

                    def _fill_need_password(xml_text):
                        if "Need Password" not in xml_text and "Password" not in xml_text:
                            return False
                        
                        # Find all EditText fields
                        et_matches = list(_re.finditer(
                            r'class="android\.widget\.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                            xml_text))
                        
                        # Fill based on number of fields (same logic as working Random VPN)
                        if len(et_matches) >= 2:
                            # Two fields - fill username in first, password in second
                            x1, y1, x2, y2 = map(int, et_matches[0].groups())
                            _type_into_field((x1+x2)//2, (y1+y2)//2, username)
                            # Dismiss keyboard and wait before filling second field
                            subprocess.run([adb,"-s",dev,"shell","input keyevent KEYCODE_BACK"], capture_output=True, timeout=3)
                            time.sleep(0.5)
                            x1, y1, x2, y2 = map(int, et_matches[1].groups())
                            _type_into_field((x1+x2)//2, (y1+y2)//2, password)
                        elif len(et_matches) == 1:
                            # One field - fill password only
                            x1, y1, x2, y2 = map(int, et_matches[0].groups())
                            _type_into_field((x1+x2)//2, (y1+y2)//2, password)
                        
                        _uidump("/sdcard/ui_ok2.xml")
                        time.sleep(0.5)
                        ui_ok2 = subprocess.run([adb,"-s",dev,"shell","cat /sdcard/ui_ok2.xml"],
                            capture_output=True, text=True, timeout=5)
                        ok_xml = ui_ok2.stdout if ui_ok2.stdout else xml_text
                        save_m = _re.search(r'text="Save Password"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', ok_xml)
                        if save_m:
                            x1,y1,x2,y2 = map(int, save_m.groups())
                            subprocess.run([adb,"-s",dev,"shell",f"input tap {(x1+x2)//2} {(y1+y2)//2}"],
                                capture_output=True, timeout=3)
                            time.sleep(0.3)
                        ok_m = _re.search(r'text="OK"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', ok_xml)
                        if ok_m:
                            x1,y1,x2,y2 = map(int, ok_m.groups())
                            subprocess.run([adb,"-s",dev,"shell",f"input tap {(x1+x2)//2} {(y1+y2)//2}"],
                                capture_output=True, timeout=3)
                            time.sleep(3)
                        else:
                            subprocess.run([adb,"-s",dev,"shell","input keyevent KEYCODE_ENTER"],
                                capture_output=True, timeout=3)
                            time.sleep(3)
                        return True

                    # Check if profile already exists using a persistent marker on sdcard
                    dest = f"/data/local/tmp/vpn/{vpn_file}"
                    import hashlib
                    _marker_hash = hashlib.md5(raw_name.encode()).hexdigest()[:8]
                    marker = f"/sdcard/frt_vpn_{_marker_hash}.marker"
                    try:
                        r = subprocess.run([adb, "-s", dev, "shell", f"test -f {marker} && echo EXISTS || echo MISSING"],
                            capture_output=True, text=True, timeout=5)
                        profile_exists = "EXISTS" in (r.stdout or "")
                    except:
                        profile_exists = False

                    # Import if needed (using WORKING ConfigConverter method)
                    # Import if needed (using WORKING ConfigConverter method)
                    if not profile_exists:
                        self._vpn_signal.emit("log", f"Importing {label} to {dev}...")
                        subprocess.run([adb, "-s", dev, "shell", "mkdir -p /data/local/tmp/vpn"],
                            capture_output=True, timeout=5)
                        subprocess.run([adb, "-s", dev, "push", vpn_file_full_path, dest],
                            capture_output=True, timeout=20)
                        subprocess.run([adb, "-s", dev, "shell", f"chmod 644 {dest}"],
                            capture_output=True, timeout=5)
                        subprocess.run([adb, "-s", dev, "shell",
                            f'am start -n de.blinkt.openvpn/.activities.ConfigConverter '
                            f'-a android.intent.action.VIEW '
                            f'-d "file://{dest}" '
                            f'-t application/x-openvpn-profile'],
                            capture_output=True, timeout=5)
                        
                        # Wait for ConfigConverter and tap save
                        import_xml = ""
                        for _ in range(6):
                            time.sleep(1)
                            try:
                                subprocess.run([adb, "-s", dev, "shell", "uiautomator dump /sdcard/ui_imp.xml"],
                                    capture_output=True, timeout=8)
                                r = subprocess.run([adb, "-s", dev, "shell", "cat /sdcard/ui_imp.xml"],
                                    capture_output=True, text=True, timeout=5)
                                import_xml = r.stdout or ""
                                if "EditText" in import_xml or "Convert Config" in import_xml:
                                    break
                            except:
                                pass
                        
                        # Tap save button (checkmark)
                        m_btn = _re.search(
                            r'class="android\.widget\.ImageButton"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                            import_xml)
                        if m_btn:
                            x1,y1,x2,y2 = map(int, m_btn.groups())
                            subprocess.run([adb, "-s", dev, "shell", f"input tap {(x1+x2)//2} {(y1+y2)//2}"],
                                capture_output=True, timeout=3)
                        else:
                            subprocess.run([adb, "-s", dev, "shell", "input tap 987 1726"],
                                capture_output=True, timeout=3)
                        time.sleep(3)
                        
                        # Press BACK to return to MainActivity
                        subprocess.run([adb, "-s", dev, "shell", "input keyevent KEYCODE_BACK"],
                            capture_output=True, timeout=3)
                        time.sleep(2)
                        subprocess.run([adb, "-s", dev, "shell", "input keyevent KEYCODE_BACK"],
                            capture_output=True, timeout=3)
                        self._vpn_signal.emit("log", f"✓ Imported {raw_name} on {dev}")
                        # Write persistent marker so we skip import next time
                        subprocess.run([adb, "-s", dev, "shell", f"touch {marker}"],
                            capture_output=True, timeout=3)

                    # Now connect (using WORKING method)
                    self._vpn_signal.emit("log", f"Connecting to {selected_location} on {dev}...")
                    
                    # Open OpenVPN MainActivity
                    subprocess.run([adb, "-s", dev, "shell",
                        "am start -n de.blinkt.openvpn/.activities.MainActivity"],
                        capture_output=True, timeout=5)
                    # Wait for OpenVPN to be in foreground (max 5s, check every 0.5s)
                    for _ in range(10):
                        time.sleep(0.5)
                        chk = subprocess.run([adb,"-s",dev,"shell",
                            "dumpsys activity activities | grep mResumedActivity"],
                            capture_output=True, text=True, timeout=3)
                        if "de.blinkt.openvpn" in (chk.stdout or ""):
                            break

                    # Disconnect existing VPN if any
                    tun_pre = subprocess.run([adb,"-s",dev,"shell","ip addr show tun0"],
                        capture_output=True, text=True, timeout=5)
                    if tun_pre.stdout and "inet" in tun_pre.stdout:
                        self._vpn_signal.emit("log", f"Disconnecting existing VPN on {dev}...")
                        subprocess.run([adb,"-s",dev,"shell",
                            "am start -n de.blinkt.openvpn/.activities.DisconnectVPN"],
                            capture_output=True, timeout=5)
                        time.sleep(2)
                        subprocess.run([adb, "-s", dev, "shell",
                            "am start -n de.blinkt.openvpn/.activities.MainActivity"],
                            capture_output=True, timeout=5)
                        time.sleep(2)

                    # Click on the profile to connect - scroll to find it
                    _uidump("/sdcard/ui_main.xml")
                    time.sleep(0.5)
                    
                    # Try to find profile without scrolling first
                    ui_main = subprocess.run([adb, "-s", dev, "shell", "cat /sdcard/ui_main.xml"],
                        capture_output=True, text=True, timeout=5)
                    cur_xml = ui_main.stdout or ""
                    tap_x, tap_y = None, None

                    for search in [raw_name, raw_name[:20]]:
                        nm = _re.search(
                            rf'text="{_re.escape(search)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                            cur_xml)
                        if nm:
                            x1,y1,x2,y2 = map(int, nm.groups())
                            tap_x, tap_y = (x1+x2)//2, (y1+y2)//2
                            break

                    # If not found on first screen, scroll to find it
                    if tap_x is None:
                        subprocess.run([adb, "-s", dev, "shell", "input swipe 540 400 540 1600 300"],
                            capture_output=True, timeout=3)
                        time.sleep(0.5)
                        for _sp in range(10):
                            _uidump(f"/sdcard/ui_sp_{_sp}.xml")
                            time.sleep(0.5)
                            r_sp = subprocess.run([adb, "-s", dev, "shell", f"cat /sdcard/ui_sp_{_sp}.xml"],
                                capture_output=True, text=True, timeout=5)
                            cur_xml = r_sp.stdout or ""
                            for search in [raw_name, raw_name[:20]]:
                                nm = _re.search(
                                    rf'text="{_re.escape(search)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                                    cur_xml)
                                if nm:
                                    x1,y1,x2,y2 = map(int, nm.groups())
                                    tap_x, tap_y = (x1+x2)//2, (y1+y2)//2
                                    break
                            if tap_x is not None:
                                break
                            subprocess.run([adb, "-s", dev, "shell", "input swipe 540 1400 540 600 400"],
                                capture_output=True, timeout=3)
                            time.sleep(0.5)

                    if tap_x is not None:
                        subprocess.run([adb, "-s", dev, "shell", f"input tap {tap_x} {tap_y}"],
                            capture_output=True, timeout=3)
                        time.sleep(2)
                        
                        # Handle password dialog
                        for _ in range(10):
                            _uidump("/sdcard/ui_pwd.xml")
                            time.sleep(1)
                            ui_pwd = subprocess.run([adb, "-s", dev, "shell", "cat /sdcard/ui_pwd.xml"],
                                capture_output=True, text=True, timeout=5)
                            if _fill_need_password(ui_pwd.stdout or ""):
                                break

                        # Verify connection
                        for _ in range(30):
                            tun = subprocess.run([adb, "-s", dev, "shell", "ip addr show tun0"],
                                capture_output=True, text=True, timeout=5)
                            if tun.stdout and "inet" in tun.stdout:
                                self._vpn_signal.emit("log", f"✓ VPN connected on {dev}")
                                self._update_proxy_in_cache(dev, f"VPN: {selected_location}")
                                return
                            time.sleep(0.5)
                        
                        self._vpn_signal.emit("log", f"✗ Connection timeout on {dev}")
                    else:
                        self._vpn_signal.emit("log", f"✗ Profile not found in UI on {dev}")
                        
                except Exception as e:
                    self._vpn_signal.emit("log", f"✗ Error on {dev}: {str(e)}")

            # Create custom non-modal progress dialog
            progress = VPNProgressDialog(
                "Connecting to VPN",
                f"Connecting {len(devices)} device(s) to {selected_location}...\nPlease wait...",
                len(devices),
                "blue",
                self
            )
            progress.show()
            progress.raise_()
            progress.activateWindow()
            QApplication.processEvents()
            
            # Store reference
            self._current_vpn_progress = progress
            
            # Connect signal to update progress
            def update_progress_slot(value, text):
                if hasattr(self, '_current_vpn_progress') and self._current_vpn_progress:
                    try:
                        self._current_vpn_progress.update_progress(value, text)
                    except:
                        pass
            
            self._vpn_progress_signal.connect(update_progress_slot)
            
            completed = [0]

            # Run all devices in parallel with animated loading
            def _run_all():
                def _connect_with_progress(dev):
                    try:
                        _connect_device(dev)
                    finally:
                        completed[0] += 1
                        # Update status text (progress bar is animated)
                        self._vpn_progress_signal.emit(
                            completed[0],
                            f"Connecting to {selected_location}...\n"
                            f"Completed: {completed[0]}/{len(devices)} devices"
                        )
                
                threads = [threading.Thread(target=_connect_with_progress, args=(dev,), daemon=True) for dev in devices]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                
                # Disconnect signal
                try:
                    self._vpn_progress_signal.disconnect(update_progress_slot)
                except:
                    pass
                
                # Close progress dialog via signal (thread-safe)
                self._vpn_done_signal.emit(len(devices))
            
            # Connect done signal to close dialog
            def close_dialog_slot(count):
                if hasattr(self, '_current_vpn_progress') and self._current_vpn_progress:
                    try:
                        self._current_vpn_progress.close()
                        self._current_vpn_progress = None
                    except:
                        pass
            
            self._vpn_done_signal.connect(close_dialog_slot)
            
            threading.Thread(target=_run_all, daemon=True).start()
    

    def _disconnect_proxy(self):
        """Disconnect OpenVPN on devices."""
        import threading, time, re as _re

        devices = self._get_devices_from_selection()
        if not devices:
            return

        self.add_activity(f"Disconnecting VPN from {len(devices)} device(s)...")

        # Create custom non-modal progress dialog
        progress = VPNProgressDialog(
            "Disconnecting VPN",
            f"Disconnecting VPN from {len(devices)} device(s)...\nPlease wait...",
            len(devices),
            "red",
            self
        )
        progress.show()
        progress.raise_()
        progress.activateWindow()
        QApplication.processEvents()
        
        # Store reference
        self._current_vpn_progress = progress
        
        # Connect signal to update progress
        def update_progress_slot(value, text):
            if hasattr(self, '_current_vpn_progress') and self._current_vpn_progress:
                try:
                    self._current_vpn_progress.update_progress(value, text)
                except:
                    pass
        
        self._vpn_progress_signal.connect(update_progress_slot)
        
        completed = [0]

        def _disconnect_device(dev):
            adb = self.adb_path
            if not hasattr(self, '_vpn_busy_devices'):
                self._vpn_busy_devices = set()
            self._vpn_busy_devices.add(dev)
            try:
                self._vpn_signal.emit("log", f"Disconnecting VPN on {dev}...")
                subprocess.run([adb, "-s", dev, "shell",
                    "am startservice -n de.blinkt.openvpn/.core.OpenVPNService --es cmd stop"],
                    capture_output=True, timeout=5)
                time.sleep(1)
                subprocess.run([adb, "-s", dev, "shell",
                    "am broadcast -a de.blinkt.openvpn.DISCONNECT_VPN --es STOP_REASON user"],
                    capture_output=True, timeout=5)
                time.sleep(2)
                subprocess.run([adb, "-s", dev, "shell",
                    "am force-stop de.blinkt.openvpn"],
                    capture_output=True, timeout=5)
                time.sleep(1)
                self._vpn_signal.emit("log", f"✓ VPN disconnected on {dev}")
                self._update_proxy_in_cache(dev, "")
            except Exception as e:
                self._vpn_signal.emit("log", f"✗ Error on {dev}: {str(e)}")
            finally:
                time.sleep(3)
                self._vpn_busy_devices.discard(dev)
                completed[0] += 1
                # Update status text (progress bar is animated)
                self._vpn_progress_signal.emit(
                    completed[0],
                    f"Disconnecting VPN...\nCompleted: {completed[0]}/{len(devices)} devices"
                )

        def _run_all():
            threads = [threading.Thread(target=_disconnect_device, args=(dev,), daemon=True) for dev in devices]
            for t in threads: t.start()
            for t in threads: t.join()
            
            # Disconnect signal
            try:
                self._vpn_progress_signal.disconnect(update_progress_slot)
            except:
                pass
            
            # Close progress dialog via signal (thread-safe)
            self._vpn_done_signal.emit(len(devices))
        
        # Connect done signal to close dialog
        def close_dialog_slot(count):
            if hasattr(self, '_current_vpn_progress') and self._current_vpn_progress:
                try:
                    self._current_vpn_progress.close()
                    self._current_vpn_progress = None
                except:
                    pass
        
        self._vpn_done_signal.connect(close_dialog_slot)
        
        # Start in background thread
        threading.Thread(target=_run_all, daemon=True).start()
    

    def _check_proxy_status(self):
        """Check current proxy status for devices."""
        import threading
        devices = self._get_devices_from_selection()
        if not devices:
            QMessageBox.warning(self, "No Devices", "Please select devices first.")
            return
        def _check_device(dev):
            adb = self.adb_path
            try:
                tun = subprocess.run([adb, "-s", dev, "shell", "ip addr show tun0"],
                    capture_output=True, text=True, timeout=5)
                if tun.stdout and "inet" in tun.stdout:
                    self._vpn_signal.emit("log", f"{dev}: VPN Connected")
                else:
                    self._vpn_signal.emit("log", f"{dev}: No VPN")
            except Exception as e:
                self._vpn_signal.emit("log", f"{dev}: Error - {str(e)}")
        threads = [threading.Thread(target=_check_device, args=(dev,), daemon=True) for dev in devices]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    
        def _run():
            for device_id in devices:
                try:
                    result = subprocess.run(
                        [self.adb_path, '-s', device_id, 'shell', 
                         'settings get global http_proxy'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        proxy = result.stdout.strip()
                        if proxy and proxy != ':0':
                            self.add_activity(f"📡 {device_id}: Connected to {proxy}")
                        else:
                            self.add_activity(f"📡 {device_id}: No proxy connected")
                    else:
                        self.add_activity(f"✗ Failed to check proxy for {device_id}")
                        
                except Exception as e:
                    self.add_activity(f"✗ Error checking {device_id}: {str(e)}")
        
        threading.Thread(target=_run, daemon=True).start()
    

    def _update_proxy_in_cache(self, device_id, proxy):
        """Update proxy information for the device (device-centric)."""
        try:
            # Update device proxy cache (for devices without assigned accounts)
            import tempfile
            cache_file = os.path.join(tempfile.gettempdir(), "frt_device_proxy_cache.json")
            
            proxy_cache = {}
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        proxy_cache = json.load(f)
                except:
                    pass
            
            proxy_cache[device_id] = proxy
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(proxy_cache, f, indent=2, ensure_ascii=False)
            
            # Also update account backup if device has an assigned account
            if os.path.exists("account_backup"):
                for folder in os.listdir("account_backup"):
                    account_info_path = os.path.join("account_backup", folder, "account_info.json")
                    if os.path.exists(account_info_path):
                        try:
                            with open(account_info_path, 'r', encoding='utf-8') as f:
                                account_data = json.load(f)
                                device_field = account_data.get('device', '')
                                if device_field and device_id in device_field:
                                    account_data['proxy'] = proxy
                                    with open(account_info_path, 'w', encoding='utf-8') as f:
                                        json.dump(account_data, f, indent=2, ensure_ascii=False)
                                    break
                        except:
                            pass
            
            # Then emit signal to update UI immediately
            self._proxy_update_signal.emit(device_id, proxy)
                
        except Exception as e:
            print(f"Error updating proxy: {e}")
            import traceback
            traceback.print_exc()

    def _on_vpn_all_done(self, device_count):
        """Show completion dialog after all VPN operations finish (runs on main thread)."""
        try:
            self.load_main_account_tab()
        except: pass
        try:
            if hasattr(self, 'load_devices_in_account_table'):
                self.load_devices_in_account_table()
        except: pass
        try:
            log_text = self.activity_log.toPlainText()
            recent = "\n".join(log_text.strip().splitlines()[-max(device_count*2, 4):]) if log_text else ""
        except:
            recent = ""
        msg = QMessageBox(self)
        msg.setWindowTitle("Done")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(f"VPN operation finished for {device_count} device(s).")
        if recent:
            msg.setInformativeText(recent)
        msg.setStyleSheet("""
            QMessageBox { background-color: #1e1e1e; }
            QMessageBox QLabel { color: #cccccc; font-size: 12px; }
            QPushButton { background-color: #4CAF50; color: white; border: none;
                border-radius: 4px; padding: 6px 16px; font-size: 12px; min-width: 80px; }
            QPushButton:hover { background-color: #45a049; }
        """)
        msg.raise_()
        msg.activateWindow()
        msg.exec()

    def _update_spoof_in_table_ui(self, device_id, fake_model):
        """Update Device Changer column in devices_table, login and auto reg tables on main thread via signal."""
        try:
            # Account tab devices_table — Device ID in col 1, Device Changer in col 6
            if hasattr(self, 'devices_table') and self.devices_table.rowCount() > 0:
                for row in range(self.devices_table.rowCount()):
                    item = self.devices_table.item(row, 1)
                    if item and item.text().strip() == device_id:
                        spoof_item = QTableWidgetItem(fake_model)
                        spoof_item.setForeground(QColor("#FF9800") if fake_model != '—' else QColor("#888888"))
                        spoof_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        self.devices_table.setItem(row, 6, spoof_item)
                        self.devices_table.viewport().update()
                        break
        except Exception as e:
            print(f"Error updating spoof in devices_table: {e}")
        try:
            # Login tab — Device ID in col 0 as "N. device_id", Device Changer in col 2
            if hasattr(self, 'login_device_select') and self.login_device_select.rowCount() > 0:
                for row in range(self.login_device_select.rowCount()):
                    item = self.login_device_select.item(row, 0)
                    if item and device_id in item.text():
                        spoof_item = QTableWidgetItem(fake_model)
                        spoof_item.setForeground(QColor("#FF9800") if fake_model != '—' else QColor("#888888"))
                        spoof_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        self.login_device_select.setItem(row, 2, spoof_item)
                        self.login_device_select.viewport().update()
                        break
        except Exception as e:
            print(f"Error updating spoof in login_device_select: {e}")
        try:
            # Auto Reg tab — Device ID in col 0 as "N. device_id", Device Changer in col 2
            if hasattr(self, 'auto_reg_device_select') and self.auto_reg_device_select.rowCount() > 0:
                for row in range(self.auto_reg_device_select.rowCount()):
                    item = self.auto_reg_device_select.item(row, 0)
                    if item and device_id in item.text():
                        spoof_item = QTableWidgetItem(fake_model)
                        spoof_item.setForeground(QColor("#FF9800") if fake_model != '—' else QColor("#888888"))
                        spoof_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        self.auto_reg_device_select.setItem(row, 2, spoof_item)
                        self.auto_reg_device_select.viewport().update()
                        break
        except Exception as e:
            print(f"Error updating spoof in auto_reg_device_select: {e}")
        try:
            # Automation tab seed_device_table — Device ID in col 0 as "N. device_id", Device Changer in col 2
            if hasattr(self, 'seed_device_table') and self.seed_device_table.rowCount() > 0:
                for row in range(self.seed_device_table.rowCount()):
                    item = self.seed_device_table.item(row, 0)
                    if item and device_id in item.text():
                        spoof_item = QTableWidgetItem(fake_model)
                        spoof_item.setForeground(QColor("#FF9800") if fake_model != '—' else QColor("#555555"))
                        spoof_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        self.seed_device_table.setItem(row, 2, spoof_item)
                        self.seed_device_table.viewport().update()
                        break
        except Exception as e:
            print(f"Error updating spoof in seed_device_table: {e}")


    def _update_proxy_in_table_ui(self, device_id, proxy):
        """Update proxy in devices_table, login and auto reg tables (runs on main thread via signal)."""
        # Normalize proxy value
        proxy_display = proxy if proxy else ""
        proxy_display_dash = proxy if proxy else "—"
        
        try:
            # Account tab devices_table — Device ID in col 1, Proxy in col 3
            if hasattr(self, 'devices_table') and self.devices_table.rowCount() > 0:
                # Temporarily disable sorting to update the data
                was_sorting = self.devices_table.isSortingEnabled()
                if was_sorting:
                    self.devices_table.setSortingEnabled(False)
                
                for row in range(self.devices_table.rowCount()):
                    item = self.devices_table.item(row, 1)
                    if item:
                        row_device = item.text().strip()
                        if row_device == device_id:
                            proxy_item = QTableWidgetItem(proxy_display_dash)
                            proxy_item.setForeground(QColor("#FF9800") if proxy else QColor("#888888"))
                            proxy_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                            self.devices_table.setItem(row, 3, proxy_item)
                            break
                
                # Re-enable sorting to refresh the visual display
                if was_sorting:
                    self.devices_table.setSortingEnabled(True)
                
                self.devices_table.viewport().update()
        except Exception as e:
            print(f"Error updating proxy in devices_table: {e}")
            import traceback
            traceback.print_exc()
        
        try:
            # Login tab — Device ID in col 0 as "N. device_id", Proxy in col 1
            if hasattr(self, 'login_device_select') and self.login_device_select.rowCount() > 0:
                for row in range(self.login_device_select.rowCount()):
                    item = self.login_device_select.item(row, 0)
                    if item and device_id in item.text():
                        proxy_item = QTableWidgetItem(proxy_display_dash)
                        proxy_item.setForeground(QColor("#FF9800") if proxy else QColor("#888888"))
                        proxy_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        self.login_device_select.setItem(row, 1, proxy_item)
                        self.login_device_select.viewport().update()
                        break
        except Exception as e:
            print(f"Error updating proxy in login_device_select: {e}")
            import traceback
            traceback.print_exc()
        
        try:
            # Auto Reg tab — Device ID in col 0 as "N. device_id", Proxy in col 1
            if hasattr(self, 'auto_reg_device_select') and self.auto_reg_device_select.rowCount() > 0:
                for row in range(self.auto_reg_device_select.rowCount()):
                    item = self.auto_reg_device_select.item(row, 0)
                    if item and device_id in item.text():
                        proxy_item = QTableWidgetItem(proxy_display_dash)
                        proxy_item.setForeground(QColor("#FF9800") if proxy else QColor("#888888"))
                        proxy_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        self.auto_reg_device_select.setItem(row, 1, proxy_item)
                        self.auto_reg_device_select.viewport().update()
                        break
        except Exception as e:
            print(f"Error updating proxy in auto_reg_device_select: {e}")
            import traceback
            traceback.print_exc()
        
        try:
            # Automation tab seed_device_table — Device ID in col 0 as "N. device_id", Proxy in col 1
            if hasattr(self, 'seed_device_table') and self.seed_device_table.rowCount() > 0:
                for row in range(self.seed_device_table.rowCount()):
                    item = self.seed_device_table.item(row, 0)
                    if item and device_id in item.text():
                        proxy_item = QTableWidgetItem(proxy_display_dash)
                        proxy_item.setForeground(QColor("#FF9800") if proxy else QColor("#555555"))
                        proxy_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        self.seed_device_table.setItem(row, 1, proxy_item)
                        self.seed_device_table.viewport().update()
                        break
        except Exception as e:
            print(f"Error updating proxy in seed_device_table: {e}")
            import traceback
            traceback.print_exc()
        
        try:
            # Accounts tab device table — Device ID in col 1 (Device Name), Proxy in col 2
            if hasattr(self, '_accounts_only_device_table') and self._accounts_only_device_table.rowCount() > 0:
                # Temporarily disable sorting to update the data
                was_sorting = self._accounts_only_device_table.isSortingEnabled()
                if was_sorting:
                    self._accounts_only_device_table.setSortingEnabled(False)
                
                for row in range(self._accounts_only_device_table.rowCount()):
                    item = self._accounts_only_device_table.item(row, 1)  # Device Name column
                    if item:
                        row_device = item.text().strip()
                        if row_device == device_id:
                            proxy_item = QTableWidgetItem(proxy_display_dash)
                            proxy_item.setForeground(QColor("#FF9800") if proxy else QColor("#888888"))
                            proxy_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                            self._accounts_only_device_table.setItem(row, 2, proxy_item)  # Proxy column
                            break
                
                # Re-enable sorting to refresh the visual display
                if was_sorting:
                    self._accounts_only_device_table.setSortingEnabled(True)
                
                self._accounts_only_device_table.viewport().update()
        except Exception as e:
            print(f"Error updating proxy in _accounts_only_device_table: {e}")
            import traceback
            traceback.print_exc()
        
        self.add_activity(f"✓ Proxy updated: {device_id} → {proxy if proxy else 'None'}")
    

    def _restore_session_from_table_row(self, row):
        """Restore session for the account at the given table row"""
        uid_item = self.account_table.item(row, 0)
        if not uid_item:
            return
        uid = uid_item.text()

        # Load full account data from backup
        backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")
        account_data = None
        for entry in os.scandir(backup_folder):
            if entry.is_dir() and entry.name.startswith(uid):
                info_path = os.path.join(entry.path, "account_info.json")
                if os.path.exists(info_path):
                    try:
                        with open(info_path, 'r', encoding='utf-8-sig') as f:
                            account_data = json.load(f)
                    except Exception:
                        pass
                break

        if not account_data:
            QMessageBox.warning(self, "Error", f"Could not load account data for UID: {uid}")
            return

        # Pick devices from login_device_select table
        checked_devices = []
        if hasattr(self, 'login_device_select'):
            selected_rows = self.login_device_select.selectionModel().selectedRows()
            for idx in selected_rows:
                item = self.login_device_select.item(idx.row(), 0)
                if item:
                    # Text is "1. device_id" - extract device_id
                    text = item.text()
                    device_id = text.split('. ', 1)[-1].strip()
                    checked_devices.append(device_id)
        
        if not checked_devices:
            QMessageBox.warning(self, "No Device", "Please open the Login tab and check or select at least one device (drag to select multiple).")
            return
        
        device_ids = checked_devices

        self.add_activity(f"Restoring session for {account_data.get('full_name', uid)}...")

        import threading
        def run():
            success, msg = self.restore_account_session(account_data, device_id)
            self.add_activity(f"{'OK' if success else 'FAIL'} {account_data.get('full_name', uid)}: {msg}")
            # Show result on main thread via a timer
            from PyQt6.QtCore import QTimer as _QTimer
            def show():
                if success:
                    QMessageBox.information(self, "Session Restored", msg)
                else:
                    QMessageBox.warning(self, "Restore Failed", msg)
            _QTimer.singleShot(0, show)

        threading.Thread(target=run, daemon=True).start()


    def _show_restore_result(self, success, msg):
        if success:
            QMessageBox.information(self, "Session Restored", msg)
        else:
            QMessageBox.warning(self, "Restore Failed", msg)
    

    def view_account_details(self, row):
        """Show detailed view of selected account"""
        uid      = self.account_table.item(row, 0).text()  if self.account_table.item(row, 0)  else ""
        name     = self.account_table.item(row, 1).text()  if self.account_table.item(row, 1)  else ""
        email    = self.account_table.item(row, 2).text()  if self.account_table.item(row, 2)  else ""
        phone    = self.account_table.item(row, 3).text()  if self.account_table.item(row, 3)  else ""
        password = self.account_table.item(row, 4).text()  if self.account_table.item(row, 4)  else ""
        birthday = self.account_table.item(row, 5).text()  if self.account_table.item(row, 5)  else ""
        gender   = self.account_table.item(row, 6).text()  if self.account_table.item(row, 6)  else ""
        device   = self.account_table.item(row, 7).text()  if self.account_table.item(row, 7)  else ""
        status   = self.account_table.item(row, 8).text()  if self.account_table.item(row, 8)  else ""
        created  = self.account_table.item(row, 9).text()  if self.account_table.item(row, 9)  else ""
        notes    = self.account_table.item(row, 10).text() if self.account_table.item(row, 10) else ""

        display_name = name if name else uid

        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_account_details"))
        dialog.setFixedSize(460, 600)
        dialog.setStyleSheet("QDialog { background-color: #1e1e1e; }")

        root = QVBoxLayout(dialog)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Cover + Avatar (overlapping) ──────────────────────────────────
        # Use a fixed-height container, cover fills top, avatar overlaps bottom
        header_container = QWidget()
        header_container.setFixedHeight(170)
        header_container.setStyleSheet("background: #1e1e1e;")

        cover_lbl = QLabel(header_container)
        cover_lbl.setGeometry(0, 0, 460, 130)
        cover_lbl.setScaledContents(True)
        cover_lbl.setStyleSheet("QLabel { background-color: #1a3a2a; border: none; }")

        initials = "".join([p[0].upper() for p in display_name.split()[:2]]) if display_name else "?"
        avatar_lbl = QLabel(initials, header_container)
        avatar_lbl.setGeometry(20, 82, 88, 88)
        avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_lbl.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                color: #4CAF50;
                font-size: 28px;
                font-weight: bold;
                border-radius: 44px;
                border: 4px solid #1e1e1e;
            }
        """)

        status_color = "#4CAF50" if status.lower() == "active" else "#f44336" if status.lower() in ("suspended", "banned") else "#FF9800"
        status_badge = QLabel(f" {status.upper()} " if status else " UNKNOWN ", header_container)
        status_badge.setGeometry(340, 138, 100, 24)
        status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {status_color};
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
                border-radius: 12px;
            }}
        """)

        root.addWidget(header_container)

        # ── Name + UID ────────────────────────────────────────────────────
        name_area = QWidget()
        name_area.setStyleSheet("background: #1e1e1e;")
        name_layout = QVBoxLayout(name_area)
        name_layout.setContentsMargins(24, 6, 24, 12)
        name_layout.setSpacing(2)
        name_lbl = QLabel(display_name)
        name_lbl.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold; background: transparent;")
        name_layout.addWidget(name_lbl)
        uid_lbl = QLabel(uid)
        uid_lbl.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
        name_layout.addWidget(uid_lbl)
        root.addWidget(name_area)

        _d = QFrame(); _d.setFrameShape(QFrame.Shape.HLine)
        _d.setStyleSheet("background: #2d2d2d; border: none; max-height: 1px;")
        root.addWidget(_d)

        # ── Info rows ─────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background: #1e1e1e; border: none; }
            QScrollBar:vertical { background: #1e1e1e; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #3d3d3d; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #4CAF50; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        info_widget = QWidget()
        info_widget.setStyleSheet("background: #1e1e1e;")
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(24, 16, 24, 16)
        info_layout.setSpacing(2)

        def _row(icon_name, icon_color, label, value, value_color="#cccccc", copyable=False):
            if not value:
                return
            w = QWidget()
            w.setStyleSheet("QWidget { background: transparent; border-radius: 4px; } QWidget:hover { background: #252526; }")
            rl = QHBoxLayout(w)
            rl.setContentsMargins(8, 8, 8, 8)
            rl.setSpacing(12)
            ico = QLabel()
            ico.setPixmap(qta.icon(icon_name, color=icon_color).pixmap(16, 16))
            ico.setFixedSize(20, 20)
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setStyleSheet("background: transparent;")
            rl.addWidget(ico)
            lbl = QLabel(label)
            lbl.setFixedWidth(80)
            lbl.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
            rl.addWidget(lbl)
            val = QLabel(value)
            val.setStyleSheet(f"color: {value_color}; font-size: 12px; background: transparent;")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            rl.addWidget(val, 1)
            if copyable:
                copy_btn = QPushButton()
                copy_btn.setIcon(qta.icon('fa5s.copy', color='#555555'))
                copy_btn.setFixedSize(24, 24)
                copy_btn.setToolTip(f"Copy {label}")
                copy_btn.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 3px; } QPushButton:hover { background: #3d3d3d; }")
                copy_btn.clicked.connect(lambda _, v=value: QApplication.clipboard().setText(v))
                rl.addWidget(copy_btn)
            info_layout.addWidget(w)

        _row('fa5s.phone',         '#4CAF50', 'Phone',    phone,    '#cccccc', copyable=True)
        _row('fa5s.envelope',      '#4CAF50', 'Email',    email,    '#cccccc', copyable=True)
        _row('fa5s.key',           '#FF9800', 'Password', password, '#FF9800', copyable=True)
        _row('fa5s.birthday-cake', '#888888', 'Birthday', birthday)
        _row('fa5s.venus-mars',    '#888888', 'Gender',   gender)
        _row('fa5s.mobile-alt',    '#888888', 'Device',   device)
        _row('fa5s.calendar-alt',  '#555555', 'Created',  created)
        _row('fa5s.sticky-note',   '#555555', 'Notes',    notes)

        info_layout.addStretch()
        scroll.setWidget(info_widget)
        root.addWidget(scroll, 1)

        # ── Footer ────────────────────────────────────────────────────────
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet("QFrame { background: #1e1e1e; border: none; border-top: 1px solid #2d2d2d; }")
        flay = QHBoxLayout(footer)
        flay.setContentsMargins(20, 0, 20, 0)
        flay.setSpacing(8)

        restore_btn = QPushButton("  Restore Session")
        restore_btn.setIcon(qta.icon('fa5s.cloud-download-alt', color='#ffffff'))
        restore_btn.setFixedHeight(36)
        restore_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d; color: #cccccc;
                border: 1px solid #3d3d3d; border-radius: 4px;
                font-size: 12px; padding: 0 14px;
            }
            QPushButton:hover { border-color: #4CAF50; color: #4CAF50; background: #333333; }
        """)
        restore_btn.clicked.connect(lambda: (dialog.accept(), self._restore_session_from_table_row(row)))
        flay.addWidget(restore_btn)
        flay.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: #ffffff;
                border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold; padding: 0 24px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        close_btn.clicked.connect(dialog.accept)
        flay.addWidget(close_btn)
        root.addWidget(footer)

        # ── Load FB images in background ──────────────────────────────────
        def _load_images():
            import urllib.request
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            def _fetch(url, w, h):
                try:
                    req = urllib.request.Request(url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    resp = urllib.request.urlopen(req, timeout=8, context=ctx)
                    data = resp.read()
                    pm = QPixmap()
                    if pm.loadFromData(data) and not pm.isNull():
                        return pm.scaled(w, h,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
                    print(f"[FB IMG] loadFromData failed for {url}")
                except Exception as e:
                    print(f"[FB IMG] fetch error: {e} — url: {url}")
                return None

            # Profile picture — redirects to CDN automatically
            profile_url = f"https://graph.facebook.com/{uid}/picture?type=large&width=200&height=200&redirect=true"
            pm = _fetch(profile_url, 88, 88)
            if pm:
                rounded = QPixmap(88, 88)
                rounded.fill(Qt.GlobalColor.transparent)
                painter = QPainter(rounded)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                from PyQt6.QtGui import QPainterPath
                path = QPainterPath()
                path.addEllipse(0, 0, 88, 88)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, pm)
                painter.end()
                def _set_avatar(p=rounded):
                    avatar_lbl.setPixmap(p)
                    avatar_lbl.setText("")
                    avatar_lbl.setStyleSheet("""
                        QLabel {
                            border-radius: 44px;
                            border: 4px solid #1e1e1e;
                            background: transparent;
                        }
                    """)
                QTimer.singleShot(0, _set_avatar)
            else:
                print(f"[FB IMG] No profile pic for UID {uid}")

            # Cover — fetch same pic at wide size, darken as cover bg
            pm_cover = _fetch(
                f"https://graph.facebook.com/{uid}/picture?type=large&width=460&height=130&redirect=true",
                460, 130
            )
            if pm_cover:
                final = QPixmap(460, 130)
                final.fill(Qt.GlobalColor.transparent)
                p2 = QPainter(final)
                p2.drawPixmap(0, 0, pm_cover)
                from PyQt6.QtGui import QColor as _QC
                p2.fillRect(0, 0, 460, 130, _QC(0, 0, 0, 150))
                p2.end()
                def _set_cover(p=final):
                    cover_lbl.setPixmap(p)
                QTimer.singleShot(0, _set_cover)

        import threading
        threading.Thread(target=_load_images, daemon=True).start()

        dialog.exec()
    

    def delete_selected_accounts(self, selected_rows):
        """Delete selected accounts from backup folder"""
        if not selected_rows:
            return
        
        # Confirm deletion
        count = len(selected_rows)
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete {count} account(s)?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        
        # Delete accounts
        backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")
        
        if not os.path.exists(backup_folder):
            QMessageBox.warning(self, "Error", "Account backup folder not found!")
            return
        
        deleted_count = 0
        errors = []
        
        # Collect account identifiers to delete (use email or phone as unique identifier)
        accounts_to_delete = []
        for row_index in selected_rows:
            row = row_index.row()
            # Get email (column 2) or phone (column 3) as identifier
            email_item = self.account_table.item(row, 2)
            phone_item = self.account_table.item(row, 3)
            
            identifier = None
            if email_item and email_item.text().strip():
                identifier = ('email', email_item.text().strip())
            elif phone_item and phone_item.text().strip():
                identifier = ('phone', phone_item.text().strip())
            
            if identifier:
                accounts_to_delete.append(identifier)
        
        # Now delete the folders
        for id_type, id_value in accounts_to_delete:
            found = False
            try:
                for folder in os.listdir(backup_folder):
                    folder_path = os.path.join(backup_folder, folder)
                    if os.path.isdir(folder_path):
                        json_file = os.path.join(folder_path, "account_info.json")
                        if os.path.exists(json_file):
                            try:
                                # Read and immediately close the file
                                with open(json_file, 'r', encoding='utf-8') as f:
                                    account_data = json.load(f)
                                
                                # Check if this is the account to delete (match by email or phone)
                                match = False
                                if id_type == 'email' and account_data.get('email', '').strip() == id_value:
                                    match = True
                                elif id_type == 'phone' and account_data.get('phone', '').strip() == id_value:
                                    match = True
                                
                                if match:
                                    # Small delay to ensure file is closed
                                    time_module.sleep(0.1)
                                    
                                    # Delete the entire folder
                                    try:
                                        shutil.rmtree(folder_path)
                                        deleted_count += 1
                                        found = True
                                        print(f"Deleted account folder: {folder_path}")
                                        break
                                    except PermissionError as pe:
                                        errors.append(f"Permission denied deleting {id_value}: {pe}")
                                        break
                                    except Exception as e:
                                        errors.append(f"Error deleting folder for {id_value}: {e}")
                                        break
                                        
                            except json.JSONDecodeError as je:
                                errors.append(f"Invalid JSON in {json_file}: {je}")
                            except Exception as e:
                                errors.append(f"Error reading {json_file}: {e}")
                
                if not found and id_value not in [e for e in errors if id_value in e]:
                    errors.append(f"Account {id_value} not found in backup folder")
                    
            except Exception as e:
                errors.append(f"Error processing {id_value}: {e}")
        
        # Small delay before refreshing
        time_module.sleep(0.2)
        
        # Refresh the table
        self.load_main_account_tab()
        
        # Show result message
        if errors:
            error_msg = "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                error_msg += f"\n... and {len(errors) - 5} more errors"
            QMessageBox.warning(
                self,
                "Deletion Complete with Errors",
                f"Successfully deleted {deleted_count} account(s).\n\nErrors:\n{error_msg}",
                QMessageBox.StandardButton.Ok
            )
        else:
            QMessageBox.information(
                self,
                "Deletion Complete",
                f"Successfully deleted {deleted_count} account(s).",
                QMessageBox.StandardButton.Ok
            )
    

    def load_custom_categories(self):
        """Load custom categories from config file"""
        try:
            from src.core.config import load_config
            
            config = load_config()
            categories = config.get('account_categories', [])
            return categories
        except Exception as e:
            print(f"Error loading categories: {e}")
        return []
    

    def save_custom_categories(self, categories):
        """Save custom categories to config file"""
        try:
            from src.core.config import load_config, save_config
            
            # Load existing config to preserve all settings
            config = load_config()
            
            # Update only the categories field
            config['account_categories'] = categories
            
            # Save back using the proper save function
            success = save_config(config)
            
            if not success:
                self.add_activity(f"⚠ Error saving categories")
            
            return success
        except Exception as e:
            print(f"Error saving categories: {e}")
            self.add_activity(f"⚠ Error saving categories: {e}")
            return False
    
            print(f"Error saving categories: {e}")
    

    def refresh_category_filter(self):
        """Refresh the category filter dropdown with custom categories"""
        try:
            # Update main Account & Device tab category filter
            current_selection = self.account_category_filter.currentText()
            
            # Block signals to prevent triggering filter during refresh
            self.account_category_filter.blockSignals(True)
            self.account_category_filter.clear()
            
            # Add default categories
            self.account_category_filter.addItems(["All", "Email", "Phone", "---"])
            
            # Add custom categories
            custom_categories = self.load_custom_categories()
            for category in custom_categories:
                self.account_category_filter.addItem(category)
            
            # Restore selection if it still exists
            index = self.account_category_filter.findText(current_selection)
            if index >= 0:
                self.account_category_filter.setCurrentIndex(index)
            else:
                self.account_category_filter.setCurrentIndex(0)  # Default to "All"
            
            # Re-enable signals
            self.account_category_filter.blockSignals(False)
            
            # Update Accounts tab category filter if it exists
            if hasattr(self, '_accounts_only_category_filter'):
                try:
                    current_selection_accounts = self._accounts_only_category_filter.currentText()
                    self._accounts_only_category_filter.blockSignals(True)
                    self._accounts_only_category_filter.clear()
                    self._accounts_only_category_filter.addItems(["All", "Email", "Phone", "---"])
                    for category in custom_categories:
                        self._accounts_only_category_filter.addItem(category)
                    
                    # Restore selection
                    index = self._accounts_only_category_filter.findText(current_selection_accounts)
                    if index >= 0:
                        self._accounts_only_category_filter.setCurrentIndex(index)
                    else:
                        self._accounts_only_category_filter.setCurrentIndex(0)
                    
                    self._accounts_only_category_filter.blockSignals(False)
                except RuntimeError:
                    # Widget was deleted, remove reference
                    delattr(self, '_accounts_only_category_filter')
        except Exception as e:
            print(f"Error refreshing category filter: {e}")
            self.add_activity(f"⚠ Error refreshing categories: {e}")
    

    def manage_categories(self):
        """Open dialog to manage custom categories"""
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_categories"))
        dialog.setFixedSize(480, 500)
        dialog.setStyleSheet("""
            QDialog { background-color: #1e1e1e; }
            QLabel { color: #cccccc; font-size: 12px; background: transparent; }
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px 12px;
                color: #cccccc;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #4CAF50; }
            QLineEdit:hover { border-color: #4CAF50; }
            QListWidget {
                background-color: #1e1e1e;
                border: none;
                color: #cccccc;
                font-size: 12px;
                outline: none;
            }
            QListWidget::item {
                padding: 0px;
                background: transparent;
            }
            QListWidget::item:selected { background: transparent; }
            QScrollBar:vertical {
                background: #1e1e1e; width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #3d3d3d; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #4CAF50; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        main_layout = QVBoxLayout(dialog)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ── Header bar ────────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet("QFrame { background: #1e1e1e; border: none; border-bottom: 1px solid #3d3d3d; }")
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(20, 0, 20, 0)
        title_lbl = QLabel("Categories")
        title_lbl.setStyleSheet("color: #4CAF50; font-size: 15px; font-weight: bold;")
        hlay.addWidget(title_lbl)
        hlay.addStretch()
        count_lbl = QLabel("0 categories")
        count_lbl.setStyleSheet("color: #555555; font-size: 11px;")
        hlay.addWidget(count_lbl)
        main_layout.addWidget(header)

        # ── Body ──────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background: #1e1e1e;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 16)
        body_layout.setSpacing(12)

        # Add row
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        new_category_input = QLineEdit()
        new_category_input.setPlaceholderText("New category name...")
        new_category_input.setFixedHeight(38)
        add_row.addWidget(new_category_input)

        add_btn = QPushButton("  Add")
        add_btn.setIcon(qta.icon('fa5s.plus', color='#ffffff'))
        add_btn.setFixedHeight(38)
        add_btn.setFixedWidth(110)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: #ffffff;
                border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        add_row.addWidget(add_btn)
        body_layout.addLayout(add_row)

        # Divider
        _d = QFrame(); _d.setFrameShape(QFrame.Shape.HLine)
        _d.setStyleSheet("background: #3d3d3d; border: none; max-height: 1px;")
        body_layout.addWidget(_d)

        # Category list
        category_list = QListWidget()
        category_list.setSpacing(2)
        body_layout.addWidget(category_list, 1)

        main_layout.addWidget(body, 1)

        # ── Footer ────────────────────────────────────────────────────────
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet("QFrame { background: #1e1e1e; border: none; border-top: 1px solid #3d3d3d; }")
        flay = QHBoxLayout(footer)
        flay.setContentsMargins(20, 0, 20, 0)
        flay.setSpacing(8)

        delete_btn = QPushButton("  Delete Selected")
        delete_btn.setIcon(qta.icon('fa5s.trash-alt', color='#f44336'))
        delete_btn.setFixedHeight(36)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #f44336;
                border: 1px solid #3d3d3d; border-radius: 4px;
                font-size: 12px; padding: 0 14px;
            }
            QPushButton:hover { border-color: #f44336; background-color: #2d2d2d; }
            QPushButton:disabled { color: #3d3d3d; border-color: #2d2d2d; }
        """)
        flay.addWidget(delete_btn)
        flay.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d; color: #cccccc;
                border: 1px solid #3d3d3d; border-radius: 4px;
                font-size: 12px; padding: 0 18px;
            }
            QPushButton:hover { background-color: #333333; border-color: #555555; }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        flay.addWidget(cancel_btn)

        save_btn = QPushButton("  Save")
        save_btn.setIcon(qta.icon('fa5s.save', color='#ffffff'))
        save_btn.setFixedHeight(36)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: #ffffff;
                border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold; padding: 0 18px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        save_btn.clicked.connect(lambda: self.save_categories_from_dialog(category_list, dialog))
        flay.addWidget(save_btn)

        main_layout.addWidget(footer)

        # ── Item builder ──────────────────────────────────────────────────
        def make_item_widget(text):
            """Build a styled row widget for a category entry."""
            w = QWidget()
            w.setStyleSheet("""
                QWidget { background-color: #252526; border-radius: 4px; }
                QWidget:hover { background-color: #2d2d2d; }
            """)
            row = QHBoxLayout(w)
            row.setContentsMargins(12, 0, 8, 0)
            row.setSpacing(8)

            dot = QLabel("●")
            dot.setStyleSheet("color: #4CAF50; font-size: 10px; background: transparent;")
            row.addWidget(dot)

            lbl = QLabel(text)
            lbl.setStyleSheet("color: #cccccc; font-size: 12px; background: transparent;")
            row.addWidget(lbl, 1)

            edit_btn = QPushButton()
            edit_btn.setIcon(qta.icon('fa5s.pen', color='#555555'))
            edit_btn.setFixedSize(26, 26)
            edit_btn.setToolTip("Rename")
            edit_btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; border-radius: 3px; }
                QPushButton:hover { background: #3d3d3d; }
            """)
            row.addWidget(edit_btn)

            return w, lbl, edit_btn

        def populate_list():
            category_list.clear()
            custom_categories = self.load_custom_categories()
            for cat in custom_categories:
                item = QListWidgetItem(category_list)
                item.setSizeHint(QSize(0, 44))
                w, lbl, edit_btn = make_item_widget(cat)

                def make_rename(it, label):
                    def do_rename():
                        old = label.text()
                        new_name, ok = QInputDialog.getText(dialog, "Rename", "New name:", text=old)
                        if ok and new_name.strip() and new_name.strip() != old:
                            label.setText(new_name.strip())
                            it.setData(Qt.ItemDataRole.UserRole, new_name.strip())
                    return do_rename

                item.setData(Qt.ItemDataRole.UserRole, cat)
                edit_btn.clicked.connect(make_rename(item, lbl))
                category_list.addItem(item)
                category_list.setItemWidget(item, w)
            count_lbl.setText(f"{category_list.count()} categor{'y' if category_list.count()==1 else 'ies'}")

        populate_list()

        def add_category():
            name = new_category_input.text().strip()
            if not name:
                return
            for i in range(category_list.count()):
                existing = category_list.item(i).data(Qt.ItemDataRole.UserRole)
                if existing == name:
                    new_category_input.setStyleSheet(new_category_input.styleSheet() + "border-color: #f44336;")
                    return
            item = QListWidgetItem(category_list)
            item.setSizeHint(QSize(0, 44))
            item.setData(Qt.ItemDataRole.UserRole, name)
            w, lbl, edit_btn = make_item_widget(name)

            def make_rename(it, label):
                def do_rename():
                    old = label.text()
                    new_name, ok = QInputDialog.getText(dialog, "Rename", "New name:", text=old)
                    if ok and new_name.strip() and new_name.strip() != old:
                        label.setText(new_name.strip())
                        it.setData(Qt.ItemDataRole.UserRole, new_name.strip())
                return do_rename

            edit_btn.clicked.connect(make_rename(item, lbl))
            category_list.addItem(item)
            category_list.setItemWidget(item, w)
            new_category_input.clear()
            new_category_input.setStyleSheet(new_category_input.styleSheet().replace("border-color: #f44336;", ""))
            count_lbl.setText(f"{category_list.count()} categor{'y' if category_list.count()==1 else 'ies'}")

        def delete_selected():
            item = category_list.currentItem()
            if item:
                category_list.takeItem(category_list.row(item))
                count_lbl.setText(f"{category_list.count()} categor{'y' if category_list.count()==1 else 'ies'}")

        add_btn.clicked.connect(add_category)
        new_category_input.returnPressed.connect(add_category)
        delete_btn.clicked.connect(delete_selected)
        category_list.itemSelectionChanged.connect(
            lambda: delete_btn.setEnabled(category_list.currentItem() is not None)
        )
        delete_btn.setEnabled(False)

        dialog.exec()
    

    def add_category_to_list(self, input_field, list_widget):
        """Add a new category to the list"""
        category_name = input_field.text().strip()
        if category_name:
            # Check if already exists
            for i in range(list_widget.count()):
                if list_widget.item(i).text() == category_name:
                    QMessageBox.warning(self, "Duplicate", "This category already exists!")
                    return
            
            list_widget.addItem(category_name)
            input_field.clear()
    

    def delete_category_from_list(self, list_widget):
        """Delete selected category from the list"""
        current_item = list_widget.currentItem()
        if current_item:
            list_widget.takeItem(list_widget.row(current_item))
    

    def save_categories_from_dialog(self, list_widget, dialog):
        """Save categories from dialog to config"""
        categories = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            val = item.data(Qt.ItemDataRole.UserRole)
            if val:
                categories.append(val)
        
        # Save to config file
        success = self.save_custom_categories(categories)
        
        if not success:
            self.add_activity("⚠ Failed to save categories")
            return
        
        # Close dialog first
        dialog.accept()
        
        # Refresh the category filter dropdown
        self.refresh_category_filter()
        
        # Show success message
        self.add_activity(f"✓ Saved {len(categories)} categor{'y' if len(categories)==1 else 'ies'}")
    

    def export_accounts(self):
        """Export accounts to CSV file"""
        if self.account_table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "No accounts to export!")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Accounts", 
            f"accounts_export_{time_module.strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    # Write headers
                    headers = []
                    for col in range(self.account_table.columnCount()):
                        headers.append(self.account_table.horizontalHeaderItem(col).text())
                    writer.writerow(headers)
                    
                    # Write data
                    for row in range(self.account_table.rowCount()):
                        row_data = []
                        for col in range(self.account_table.columnCount()):
                            item = self.account_table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
                
                QMessageBox.information(self, "Success", f"Exported {self.account_table.rowCount()} accounts to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to export accounts:\n{str(e)}")
    

    def _parse_acc_info(self, acc_info_path):
        """
        Parse Acc info file. Supports two formats:
        1. Pipe-delimited: UID|Password|cookies  (one account per line)
        2. Key:Value pairs: UID: 123, Name: John, etc.
        Returns list of account dicts.
        """
        accounts = []
        try:
            with open(acc_info_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().strip()

            lines = [l.strip() for l in content.splitlines() if l.strip()]

            # Detect format: if first non-empty line has | and looks like UID|pass|cookies
            first_line = lines[0] if lines else ''
            if '|' in first_line and not ':' in first_line.split('|')[0]:
                # Pipe-delimited format: UID|Password|cookies
                for line in lines:
                    parts = line.split('|', 2)
                    if len(parts) >= 2:
                        uid = parts[0].strip()
                        password = parts[1].strip()
                        cookies = parts[2].strip() if len(parts) > 2 else ''
                        # Extract c_user from cookies as uid confirmation
                        import re
                        c_user_match = re.search(r'c_user=(\d+)', cookies)
                        if c_user_match:
                            uid = c_user_match.group(1)
                        accounts.append({
                            'uid': uid,
                            'password': password,
                            'cookies': cookies,
                            'name': '',
                            'email': '',
                            'phone': '',
                            'birthday': '',
                            'gender': '',
                        })
            else:
                # Key:Value format
                data = {}
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        data[key.strip()] = value.strip()
                if data:
                    accounts.append({
                        'uid': data.get('UID', data.get('Uid', '')),
                        'name': data.get('Name', data.get('Full Name', '')),
                        'email': data.get('Email', ''),
                        'phone': data.get('Phone', data.get('Phone Number', '')),
                        'password': data.get('Password', data.get('Pass', '')),
                        'birthday': data.get('Birthday', data.get('Date of Birth', '')),
                        'gender': data.get('Gender', ''),
                        'cookies': '',
                    })
        except Exception as e:
            print(f"Error parsing acc info: {e}")

        return accounts


    def _find_account_folders(self, root_path):
        """
        Find account folders. Supports:
        1. root_path has Acc info / Acc info.txt directly (single folder = one or many accounts)
        2. root_path contains subfolders each with Acc info
        3. root_path contains raw .tar files (Profile backups) - NEW
        Returns list of account folder paths.
        """
        acc_info_names = {'acc info', 'acc info.txt', 'account_info.json'}

        def has_acc_info(folder):
            try:
                return any(f.lower() in acc_info_names for f in os.listdir(folder))
            except Exception:
                return False

        # Case 1: selected folder itself has Acc info
        if has_acc_info(root_path):
            return [root_path]

        # Case 2: subfolders are accounts
        account_folders = []
        try:
            for entry in os.scandir(root_path):
                if entry.is_dir() and has_acc_info(entry.path):
                    account_folders.append(entry.path)
        except Exception:
            pass

        # Case 3: deeper nesting
        if not account_folders:
            for root, dirs, files in os.walk(root_path):
                if any(f.lower() in acc_info_names for f in files):
                    account_folders.append(root)
        
        # Case 4: NEW - folder contains raw .tar files (Profile backups)
        # Convert them to importable format on-the-fly
        if not account_folders:
            try:
                # Check if folder contains .tar files
                all_files = os.listdir(root_path)
                tar_files = [f for f in all_files if f.endswith('.tar') and os.path.isfile(os.path.join(root_path, f))]
                
                if tar_files:
                    print(f"Found {len(tar_files)} tar files in {root_path}")
                    
                    # Create temp folders for tar files
                    import tempfile
                    temp_base = tempfile.mkdtemp(prefix="frt_tar_import_")
                    print(f"Created temp folder: {temp_base}")
                    
                    for tar_file in tar_files:
                        try:
                            # Extract UID from filename (e.g., 61586927747389.tar)
                            uid = os.path.splitext(tar_file)[0]
                            if not uid.isdigit() or len(uid) < 10:
                                print(f"Skipping {tar_file}: invalid UID format")
                                continue
                            
                            print(f"Processing {tar_file} (UID: {uid})")
                            
                            # Create account folder structure
                            acc_folder = os.path.join(temp_base, f"{uid}_tar_import")
                            os.makedirs(acc_folder, exist_ok=True)
                            
                            # Copy tar file to Profile info folder
                            profile_folder = os.path.join(acc_folder, "Profile info")
                            os.makedirs(profile_folder, exist_ok=True)
                            
                            tar_path = os.path.join(root_path, tar_file)
                            dest_tar = os.path.join(profile_folder, f"{uid}.tar.gz")
                            shutil.copy2(tar_path, dest_tar)
                            print(f"  Copied to: {dest_tar}")
                            
                            # Create placeholder Acc info
                            acc_info_path = os.path.join(acc_folder, "Acc info")
                            with open(acc_info_path, 'w', encoding='utf-8') as f:
                                f.write(f"{uid}|EDIT_PASSWORD|c_user={uid}; xs=EDIT_XS; fr=EDIT_FR; datr=EDIT_DATR\n")
                            print(f"  Created Acc info")
                            
                            # Create account_info.json
                            account_info = {
                                "account_uid": uid,
                                "full_name": f"Account {uid}",
                                "first_name": "Account",
                                "last_name": uid,
                                "email": "",
                                "phone": "",
                                "password": "EDIT_PASSWORD",
                                "birthday": "",
                                "gender": "",
                                "cookies": f"c_user={uid}; xs=EDIT_XS; fr=EDIT_FR; datr=EDIT_DATR",
                                "device_info": {},
                                "status": "active",
                                "created_at": "2026-04-26",
                                "imported": True,
                                "notes": "Imported from tar file - EDIT PASSWORD AND COOKIES"
                            }
                            
                            json_path = os.path.join(acc_folder, "account_info.json")
                            with open(json_path, 'w', encoding='utf-8') as f:
                                json.dump(account_info, f, indent=2, ensure_ascii=False)
                            print(f"  Created account_info.json")
                            
                            account_folders.append(acc_folder)
                            print(f"  ✓ Added {acc_folder}")
                            
                        except Exception as e:
                            print(f"Error processing {tar_file}: {e}")
                            import traceback
                            traceback.print_exc()
                            continue
                    
                    # Store temp path for cleanup later
                    if account_folders:
                        self._tar_import_temp_path = temp_base
                        print(f"Total account folders created: {len(account_folders)}")
                    else:
                        # Clean up if no accounts were created
                        import shutil
                        shutil.rmtree(temp_base, ignore_errors=True)
                        
            except Exception as e:
                print(f"Error scanning for tar files: {e}")
                import traceback
                traceback.print_exc()

        return account_folders


    def assign_category_to_accounts(self, selected_rows, category):
        """Assign a category to selected accounts"""
        backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")
        updated_count = 0
        errors = []
        
        for row_index in selected_rows:
            row = row_index.row()
            # Column 1 is UID
            uid_item = self.account_table.item(row, 1)
            
            if uid_item and uid_item.text().strip() and uid_item.text() != "—":
                uid = uid_item.text().strip()
                
                # Find and update the account by UID
                for folder in os.listdir(backup_folder):
                    folder_path = os.path.join(backup_folder, folder)
                    if os.path.isdir(folder_path):
                        json_file = os.path.join(folder_path, "account_info.json")
                        if os.path.exists(json_file):
                            try:
                                # Read account data
                                with open(json_file, 'r', encoding='utf-8') as f:
                                    account_data = json.load(f)
                                
                                # Match by UID
                                stored_uid = account_data.get('account_uid', account_data.get('uid', account_data.get('id', folder.split('_')[0])))
                                
                                if str(stored_uid) == str(uid):
                                    # Update category (empty string removes category)
                                    if category:
                                        account_data['category'] = category
                                    else:
                                        # Remove category field if setting to empty
                                        account_data.pop('category', None)
                                    
                                    # Save with retry logic for Windows permission issues
                                    max_retries = 3
                                    for attempt in range(max_retries):
                                        try:
                                            with open(json_file, 'w', encoding='utf-8') as f:
                                                json.dump(account_data, f, indent=4, ensure_ascii=False)
                                            updated_count += 1
                                            break
                                        except PermissionError as pe:
                                            if attempt < max_retries - 1:
                                                time.sleep(0.1)
                                                continue
                                            else:
                                                # Try temp file method as fallback
                                                try:
                                                    import tempfile
                                                    temp_fd, temp_path = tempfile.mkstemp(suffix='.json', dir=folder_path)
                                                    with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                                                        json.dump(account_data, f, indent=4, ensure_ascii=False)
                                                    
                                                    # Try to replace original file
                                                    if os.path.exists(json_file):
                                                        os.remove(json_file)
                                                    os.rename(temp_path, json_file)
                                                    updated_count += 1
                                                    break
                                                except Exception as temp_err:
                                                    errors.append(f"UID {uid}: {str(pe)}")
                                                    break
                                    break
                            except Exception as e:
                                errors.append(f"UID {uid}: {str(e)}")
                                print(f"Error updating category for UID {uid}: {e}")
        
        # Refresh table to show updated categories
        self.load_main_account_tab()
        
        # Show results
        if category:
            if errors:
                self.add_activity(f"⚠ Assigned category '{category}' to {updated_count}/{len(selected_rows)} account(s). {len(errors)} failed.")
            else:
                self.add_activity(f"✓ Assigned category '{category}' to {updated_count} account(s)")
        else:
            if errors:
                self.add_activity(f"⚠ Removed category from {updated_count}/{len(selected_rows)} account(s). {len(errors)} failed.")
            else:
                self.add_activity(f"✓ Removed category from {updated_count} account(s)")
        
        # Show detailed errors if any
        if errors and len(errors) <= 5:
            for err in errors:
                print(f"  - {err}")
    

    def _maxchange_change_device_from_account(self, brand_filter=None):
        """Apply MaxChange device spoofing to devices from selected accounts using FAST broadcast mode (background thread)."""
        selected_rows = self.account_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Account Selected", "Please select at least one account from the table.")
            return
        
        # Extract device IDs from selected accounts
        device_ids = []
        for row_index in selected_rows:
            row = row_index.row()
            device_item = self.account_table.item(row, 1)  # Device ID column
            if device_item:
                device_id = device_item.text().strip()
                if device_id and device_id not in device_ids and device_id != "—":
                    device_ids.append(device_id)
        
        if not device_ids:
            QMessageBox.warning(self, "No Devices Found", 
                              "Selected accounts don't have devices assigned.\n\nPlease click 'Load Devices' first.")
            return
        
        brand_name = brand_filter if brand_filter else "Random"
        self.add_activity(f"🔄 Starting MaxChange ({brand_name}) for {len(device_ids)} device(s) from accounts - Fast Broadcast Mode...")
        
        # Create and start worker thread
        adb_path = "C:\\Users\\KLS COMPUTER\\Desktop\\FRT\\platform-tools\\adb.exe"
        base_dir = _PROJECT_ROOT
        
        # Check if _MaxChangeWorker class exists
        if not hasattr(sys.modules[__name__], '_MaxChangeWorker'):
            QMessageBox.critical(self, "Error", "_MaxChangeWorker class not found!")
            return
        
        from src.workers.maxchange_worker import MaxChangeWorker as _MaxChangeWorker
        
        self._maxchange_worker = _MaxChangeWorker(device_ids, brand_filter, adb_path, base_dir)
        self._maxchange_worker.progress.connect(self.add_activity)
        self._maxchange_worker.finished.connect(self._on_maxchange_finished)
        self._maxchange_worker.spoof_updated.connect(self._update_spoof_in_table_ui)
        self._maxchange_worker.start()
    

    def _maxchange_check_device_from_account(self):
        """Check current MaxChange device info for devices from selected accounts."""
        selected_rows = self.account_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Account Selected", "Please select at least one account from the table.")
            return
        
        # Extract device IDs from selected accounts
        device_ids = []
        for row_index in selected_rows:
            row = row_index.row()
            device_item = self.account_table.item(row, 1)  # Device ID column
            if device_item:
                device_id = device_item.text().strip()
                if device_id and device_id not in device_ids and device_id != "—":
                    device_ids.append(device_id)
        
        if not device_ids:
            QMessageBox.warning(self, "No Devices Found", 
                              "Selected accounts don't have devices assigned.\n\nPlease click 'Load Devices' first.")
            return
        
        info_text = "MaxChange Device Information\n" + "="*50 + "\n\n"
        
        for device_id in device_ids:
            adb_path = "C:\\Users\\KLS COMPUTER\\Desktop\\FRT\\platform-tools\\adb.exe"
            cmd = f'"{adb_path}" -s {device_id} shell su -c "cat /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml"'
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                xml_text = result.stdout.strip()
                
                if xml_text:
                    import re
                    brand = re.search(r'name="brand"[^>]*>([^<]+)<', xml_text)
                    model = re.search(r'name="model"[^>]*>([^<]+)<', xml_text)
                    fp = re.search(r'name="fingerprint"[^>]*>([^<]+)<', xml_text)
                    
                    info_text += f"Device: {device_id}\n"
                    info_text += f"Brand: {brand.group(1) if brand else 'N/A'}\n"
                    info_text += f"Model: {model.group(1) if model else 'N/A'}\n"
                    info_text += f"Fingerprint: {fp.group(1)[:80] if fp else 'N/A'}...\n"
                    info_text += "\n"
                else:
                    info_text += f"Device: {device_id}\n"
                    info_text += "Status: MaxChange not configured or no root access\n\n"
            except Exception as e:
                info_text += f"Device: {device_id}\n"
                info_text += f"Error: {str(e)[:100]}\n\n"
        
        # Show dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("MaxChange Device Info")
        dialog.setMinimumSize(600, 400)
        layout = QVBoxLayout(dialog)
        
        text_edit = QTextEdit()
        text_edit.setPlainText(info_text)
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #cccccc;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(text_edit)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        layout.addWidget(close_btn)
        
        dialog.exec()

