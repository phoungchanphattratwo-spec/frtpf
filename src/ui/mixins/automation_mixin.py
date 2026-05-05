"""
AutomationMixin — Automation Mixin methods.

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

import sys, os, json, subprocess, threading, time, tempfile, re, requests

from src.i18n.engine import (
    translate as _T, register_widget as _reg,
    _CURRENT_LANG, _get_khmer_font, _REGISTRY as _I18N_REGISTRY,
)
from src.i18n.translations import TRANSLATIONS
from src.automation.url_normalizer import normalize_facebook_url, URL_TYPE_LABELS as _URL_TYPE_LABELS
from src.core.config import CONFIG_FILE
from src.ui.safe_combobox import SafeComboBox

# Project root — 3 levels up from src/ui/mixins/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.core.subprocess_utils import safe_subprocess_run
# Lazy import — registration pulls in appium/selenium (300-700ms cold-start)
# Import only when an automation session actually starts
# MaxChangeWorker lazy-imported in methods that use it (saves 75ms cold-start)

class AutomationMixin:
    """Mixin — methods are injected into MainWindow via multiple inheritance."""

    def close_main_automation_tab(self):
        """Close the main Automation tab"""
        # Find the Automation tab by name instead of using stored index
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Automation":
                self.tab_widget.removeTab(i)
                self.automation_tab_index = -1  # Mark as closed
                return
        # Config will be saved automatically when app closes


    def open_automation_tab(self):
        """Open or restore the Automation tab"""
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Automation":
                self.tab_widget.setCurrentIndex(i)
                return
        if hasattr(self, 'main_automation_tab') and self.main_automation_tab:
            self.automation_tab_index = self.tab_widget.addTab(self.main_automation_tab, "Automation")
            self.tab_widget.setCurrentIndex(self.automation_tab_index)
            automation_close_btn = QPushButton("×")
            automation_close_btn.setFixedSize(20, 20)
            automation_close_btn.setStyleSheet("""
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
            automation_close_btn.clicked.connect(self.close_main_automation_tab)
            self.tab_widget.tabBar().setTabButton(self.automation_tab_index, QTabBar.ButtonPosition.RightSide, automation_close_btn)


    def _build_automation_tab(self):
        """Build the 3-panel Automation tab: Accounts | Seeding | Devices+Settings"""
        _PANEL_STYLE = "QFrame { background-color: #1e1e1e; border: none; }"
        _TOOLBAR_STYLE = "QFrame { background-color: #1e1e1e; border: none; border-bottom: 1px solid #3d3d3d; }"
        _TITLE_STYLE = "color: #4CAF50; font-size: 14px; font-weight: bold; background: transparent;"
        _BADGE_STYLE = "QLabel { background: transparent; color: #555555; font-size: 11px; padding: 0; border: none; }"
        _TABLE_STYLE = """
            QTableWidget { background-color: #1a1a1a; border: none; color: #cccccc;
                font-size: 12px; gridline-color: transparent; selection-background-color: transparent; outline: none; }
            QTableWidget::item { padding: 8px 10px; border: none; border-bottom: 1px solid #2a2a2a; }
            QTableWidget::item:hover { background-color: transparent; }
            QTableWidget::item:selected { background-color: rgba(76,175,80,0.15); color: #4CAF50; }
            QHeaderView::section { background-color: #252525; color: #666666; padding: 6px 10px;
                border: none; border-bottom: 1px solid #3d3d3d; font-weight: 600; font-size: 10px; text-transform: uppercase; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: #3d3d3d; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #4CAF50; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal { background: transparent; height: 6px; }
            QScrollBar::handle:horizontal { background: #3d3d3d; border-radius: 3px; min-width: 20px; }
            QScrollBar::handle:horizontal:hover { background: #4CAF50; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        """
        _BTN_GREEN = """QPushButton { background-color: #4CAF50; color: #ffffff; border: none;
            border-radius: 5px; padding: 7px 14px; font-size: 12px; font-weight: 600; }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #388E3C; }
            QPushButton:disabled { background-color: #2a2a2a; color: #555555; }"""
        _INPUT_STYLE = """QTextEdit, QLineEdit { background-color: #252525; color: #cccccc; border: 1px solid #3d3d3d;
            border-radius: 5px; padding: 6px 10px; font-size: 12px; }
            QTextEdit:focus, QLineEdit:focus { border-color: #4CAF50; }"""
        _SPIN_STYLE = """QSpinBox { background-color: #252525; color: #cccccc; border: 1px solid #3d3d3d;
            border-radius: 5px; padding: 4px 8px; font-size: 12px; }
            QSpinBox:focus { border-color: #4CAF50; }
            QSpinBox::up-button, QSpinBox::down-button { width: 16px; background: #2d2d2d; border: none; }"""
        _COMBO_STYLE = """QComboBox { background-color: #252525; color: #cccccc; border: 1px solid #3d3d3d;
            border-radius: 5px; padding: 5px 10px; font-size: 12px; }
            QComboBox:focus { border-color: #4CAF50; }
            QComboBox QAbstractItemView { background-color: #252525; color: #cccccc; selection-background-color: #2d5a2d; }"""
        _SECTION_LABEL = "color: #4CAF50; font-size: 11px; font-weight: 700; background: transparent; text-transform: uppercase; letter-spacing: 1px;"
        _CHECK_STYLE = """QCheckBox { color: #cccccc; font-size: 12px; background: transparent; spacing: 6px; }
            QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 1px solid #3d3d3d; background: #252525; }
            QCheckBox::indicator:checked { background-color: #4CAF50; border-color: #4CAF50; }"""

        tab = QWidget()
        tab.setStyleSheet("background-color: #0f0f0f;")
        main_layout = QHBoxLayout(tab)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ── LEFT PANEL: Accounts (22%) ────────────────────────────────────
        left_panel = QFrame()
        left_panel.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-right: 1px solid #2a2a2a; }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(0)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_toolbar = QFrame(); left_toolbar.setFixedHeight(52); left_toolbar.setStyleSheet(_TOOLBAR_STYLE)
        lt_layout = QHBoxLayout(left_toolbar); lt_layout.setContentsMargins(14, 0, 10, 0); lt_layout.setSpacing(8)
        lt_title = QLabel("Accounts"); lt_title.setStyleSheet(_TITLE_STYLE)
        self.auto_seed_account_badge = QLabel("0 accounts"); self.auto_seed_account_badge.setStyleSheet(_BADGE_STYLE)
        lt_layout.addWidget(lt_title); lt_layout.addStretch()
        seed_add_acc_btn = QPushButton("  Add Account")
        seed_add_acc_btn.setIcon(qta.icon('fa5s.plus', color='#ffffff'))
        seed_add_acc_btn.setFixedHeight(32)
        seed_add_acc_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: #ffffff; font-size: 12px;
                font-weight: 600; padding: 0 14px; border: none; border-radius: 4px; }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        seed_add_acc_btn.clicked.connect(self._seed_select_accounts)
        lt_layout.addWidget(seed_add_acc_btn)

        seed_clear_acc_btn = QPushButton()
        seed_clear_acc_btn.setIcon(qta.icon('fa5s.trash-alt', color='#f44336'))
        seed_clear_acc_btn.setFixedSize(32, 32)
        seed_clear_acc_btn.setToolTip("Clear all accounts")
        seed_clear_acc_btn.setStyleSheet("""
            QPushButton { background-color: #1e1e1e; border: 1px solid #2a2a2a; border-radius: 4px; }
            QPushButton:hover { background-color: #252525; border-color: #3e3e42; }
        """)
        seed_clear_acc_btn.clicked.connect(self._seed_clear_accounts)
        lt_layout.addWidget(seed_clear_acc_btn)
        left_layout.addWidget(left_toolbar)

        self.seeding_account_table = QTableWidget()
        self.seeding_account_table.setColumnCount(4)
        self.seeding_account_table.setHorizontalHeaderLabels(["#", "UID", "Name", "Status"])
        self.seeding_account_table.setStyleSheet(_TABLE_STYLE)
        self.seeding_account_table.verticalHeader().setVisible(False)
        self.seeding_account_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.seeding_account_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.seeding_account_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.seeding_account_table.setShowGrid(False)
        self.seeding_account_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.seeding_account_table.verticalHeader().setDefaultSectionSize(36)
        acc_hdr = self.seeding_account_table.horizontalHeader()
        acc_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed); self.seeding_account_table.setColumnWidth(0, 32)
        acc_hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        acc_hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        acc_hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        left_layout.addWidget(self.seeding_account_table, 1)

        left_stats = QFrame(); left_stats.setFixedHeight(36)
        left_stats.setStyleSheet("QFrame { background: #1e1e1e; border: none; border-top: 1px solid #2a2a2a; }")
        ls_layout = QHBoxLayout(left_stats); ls_layout.setContentsMargins(14, 0, 14, 0); ls_layout.setSpacing(16)
        self._seed_stat_total = QLabel("Total: 0"); self._seed_stat_total.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
        self._seed_stat_done  = QLabel("Done: 0");  self._seed_stat_done.setStyleSheet("color: #4CAF50; font-size: 11px; background: transparent;")
        self._seed_stat_fail  = QLabel("Failed: 0"); self._seed_stat_fail.setStyleSheet("color: #f44336; font-size: 11px; background: transparent;")
        for w in [self._seed_stat_total, self._seed_stat_done, self._seed_stat_fail]: ls_layout.addWidget(w)
        ls_layout.addStretch()
        left_layout.addWidget(left_stats)
        main_layout.addWidget(left_panel, 30)

        # ── CENTER PANEL: Seeding React/Comment (48%) ─────────────────────
        center_panel = QFrame()
        center_panel.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-right: 1px solid #2a2a2a; }")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setSpacing(0)
        center_layout.setContentsMargins(0, 0, 0, 0)

        center_toolbar = QFrame(); center_toolbar.setFixedHeight(52); center_toolbar.setStyleSheet(_TOOLBAR_STYLE)
        ct_layout = QHBoxLayout(center_toolbar); ct_layout.setContentsMargins(14, 0, 14, 0); ct_layout.setSpacing(10)
        ct_title = QLabel("Seeding"); ct_title.setStyleSheet(_TITLE_STYLE)
        ct_layout.addWidget(ct_title); ct_layout.addStretch()

        _toggle_on  = "QPushButton { background: rgba(76,175,80,0.15); color: #4CAF50; border: 1px solid #4CAF50; border-radius: 5px; padding: 5px 12px; font-size: 12px; font-weight: 600; }"
        _toggle_off = "QPushButton { background: transparent; color: #666666; border: 1px solid #3d3d3d; border-radius: 5px; padding: 5px 12px; font-size: 12px; } QPushButton:hover { background: #2a2a2a; color: #cccccc; }"
        self._seed_react_btn = QPushButton("  React"); self._seed_react_btn.setIcon(qta.icon('fa5s.thumbs-up', color='#4CAF50'))
        self._seed_react_btn.setCheckable(True); self._seed_react_btn.setChecked(True); self._seed_react_btn.setStyleSheet(_toggle_on)
        self._seed_comment_btn = QPushButton("  Comment"); self._seed_comment_btn.setIcon(qta.icon('fa5s.comment', color='#888888'))
        self._seed_comment_btn.setCheckable(True); self._seed_comment_btn.setStyleSheet(_toggle_off)

        from PyQt6.QtWidgets import QStackedWidget
        self.seeding_stack = QStackedWidget(); self.seeding_stack.setStyleSheet("background: transparent;")

        def _switch_react():
            self._seed_react_btn.setChecked(True); self._seed_comment_btn.setChecked(False)
            self._seed_react_btn.setStyleSheet(_toggle_on); self._seed_comment_btn.setStyleSheet(_toggle_off)
            self._seed_react_btn.setIcon(qta.icon('fa5s.thumbs-up', color='#4CAF50'))
            self._seed_comment_btn.setIcon(qta.icon('fa5s.comment', color='#888888'))
            self.seeding_stack.setCurrentIndex(0)
        def _switch_comment():
            self._seed_comment_btn.setChecked(True); self._seed_react_btn.setChecked(False)
            self._seed_comment_btn.setStyleSheet(_toggle_on); self._seed_react_btn.setStyleSheet(_toggle_off)
            self._seed_comment_btn.setIcon(qta.icon('fa5s.comment', color='#4CAF50'))
            self._seed_react_btn.setIcon(qta.icon('fa5s.thumbs-up', color='#888888'))
            self.seeding_stack.setCurrentIndex(1)
        self._seed_react_btn.clicked.connect(_switch_react)
        self._seed_comment_btn.clicked.connect(_switch_comment)
        ct_layout.addWidget(self._seed_react_btn); ct_layout.addWidget(self._seed_comment_btn)
        center_layout.addWidget(center_toolbar)

        # Wrap seeding stack in a scroll area so content is never clipped
        _seed_scroll = QScrollArea()
        _seed_scroll.setWidgetResizable(True)
        _seed_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollBar:vertical { background: transparent; width: 6px; } QScrollBar::handle:vertical { background: #3d3d3d; border-radius: 3px; }")

        # React page
        react_page = QWidget(); react_page.setStyleSheet("background: transparent;")
        rp_layout = QVBoxLayout(react_page); rp_layout.setSpacing(14); rp_layout.setContentsMargins(16, 16, 16, 16)
        _url_lbl = QLabel("Post URL / ID"); _url_lbl.setStyleSheet(_SECTION_LABEL)
        self.seed_post_url_input = QLineEdit()
        self.seed_post_url_input.setPlaceholderText(
            "Paste any Facebook URL or post ID — post, photo, video, reel, group, share link, fb.me/...")
        self.seed_post_url_input.setStyleSheet(_INPUT_STYLE); self.seed_post_url_input.setFixedHeight(36)
        # Live URL-type badge
        self._seed_react_url_badge = QLabel("")
        self._seed_react_url_badge.setStyleSheet("color: #888888; font-size: 11px; padding: 0 2px;")
        def _update_react_url_badge(text):
            t = text.strip()
            if not t:
                self._seed_react_url_badge.setText("")
                return
            _, utype = normalize_facebook_url(t)
            label, color = _URL_TYPE_LABELS.get(utype, ("🔗 URL", "#888888"))
            self._seed_react_url_badge.setText(f"<span style='color:{color};'>{label}</span>")
        self.seed_post_url_input.textChanged.connect(_update_react_url_badge)
        rp_layout.addWidget(_url_lbl); rp_layout.addWidget(self.seed_post_url_input)
        rp_layout.addWidget(self._seed_react_url_badge)
        _react_type_lbl = QLabel("Reaction Types"); _react_type_lbl.setStyleSheet(_SECTION_LABEL)
        rp_layout.addWidget(_react_type_lbl)
        
        # Reaction checkboxes with Facebook PNG icons
        # When frozen by PyInstaller, data files live in sys._MEIPASS
        # When running from source, reactions/ is at the project root
        if getattr(sys, '_MEIPASS', None):
            _base = sys._MEIPASS
        else:
            _base = _PROJECT_ROOT
        _react_dir = os.path.join(_base, "reactions")
        def _react_icon(filename):
            path = os.path.join(_react_dir, filename)
            if not os.path.exists(path):
                return qta.icon('fa5s.heart', color='#F7B125')
            if filename.lower().endswith('.svg'):
                try:
                    from PyQt6.QtSvg import QSvgRenderer
                    renderer = QSvgRenderer(path)
                    px = QPixmap(20, 20)
                    px.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(px)
                    renderer.render(painter)
                    painter.end()
                    return QIcon(px)
                except Exception:
                    return qta.icon('fa5s.laugh', color='#F7B125')
            px = QPixmap(path).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            return QIcon(px)

        self.seed_react_like_cb  = QCheckBox("Like");  self.seed_react_like_cb.setStyleSheet(_CHECK_STYLE);  self.seed_react_like_cb.setChecked(True)
        self.seed_react_love_cb  = QCheckBox("Love");  self.seed_react_love_cb.setStyleSheet(_CHECK_STYLE)
        self.seed_react_care_cb  = QCheckBox("Care");  self.seed_react_care_cb.setStyleSheet(_CHECK_STYLE)
        self.seed_react_haha_cb  = QCheckBox("Haha");  self.seed_react_haha_cb.setStyleSheet(_CHECK_STYLE)
        self.seed_react_wow_cb   = QCheckBox("Wow");   self.seed_react_wow_cb.setStyleSheet(_CHECK_STYLE)
        self.seed_react_sad_cb   = QCheckBox("Sad");   self.seed_react_sad_cb.setStyleSheet(_CHECK_STYLE)
        self.seed_react_angry_cb = QCheckBox("Angry"); self.seed_react_angry_cb.setStyleSheet(_CHECK_STYLE)

        self.seed_react_like_cb.setIcon(_react_icon("facebook-new-like-symbol-32.png"))
        self.seed_react_love_cb.setIcon(_react_icon("facebook-love-png-3.png"))
        self.seed_react_care_cb.setIcon(_react_icon("care.webp"))
        self.seed_react_haha_cb.setIcon(_react_icon("facebook-reaction-haha.svg"))
        self.seed_react_wow_cb.setIcon(_react_icon("wow.webp"))
        self.seed_react_sad_cb.setIcon(_react_icon("sad.png"))
        self.seed_react_angry_cb.setIcon(_react_icon("facebook-angry-logo-png-transparent.png"))

        _react_row = QHBoxLayout(); _react_row.setSpacing(12)
        for _cb in [self.seed_react_like_cb, self.seed_react_love_cb, self.seed_react_care_cb,
                    self.seed_react_haha_cb, self.seed_react_wow_cb, self.seed_react_sad_cb, self.seed_react_angry_cb]:
            _react_row.addWidget(_cb)
        _react_row.addStretch()
        rp_layout.addLayout(_react_row)

        # Share option
        self.seed_share_cb = QCheckBox("Share post after reacting")
        self.seed_share_cb.setStyleSheet(_CHECK_STYLE)
        self.seed_share_cb.setIcon(qta.icon('fa5s.share', color='#4CAF50'))
        rp_layout.addWidget(self.seed_share_cb)

        _comment_lbl = QLabel("Comment (optional)"); _comment_lbl.setStyleSheet(_SECTION_LABEL)
        rp_layout.addWidget(_comment_lbl)

        # Scrollable list of checkbox + comment lines
        self._seed_react_comment_scroll = QScrollArea()
        self._seed_react_comment_scroll.setWidgetResizable(True)
        self._seed_react_comment_scroll.setMinimumHeight(120)
        self._seed_react_comment_scroll.setSizePolicy(
            self._seed_react_comment_scroll.sizePolicy().horizontalPolicy(),
            __import__('PyQt6.QtWidgets', fromlist=['QSizePolicy']).QSizePolicy.Policy.Expanding
        )
        self._seed_react_comment_scroll.setStyleSheet("""
            QScrollArea { background: #1a1a1a; border: 1px solid #3d3d3d; border-radius: 6px; }
            QScrollArea:focus { border-color: #4CAF50; }
            QScrollArea > QWidget > QWidget { background: #1a1a1a; border-radius: 6px; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: #3d3d3d; border-radius: 3px; }
        """)
        self._seed_react_comment_scroll.viewport().setStyleSheet("background: #1a1a1a; border-radius: 6px;")
        self._seed_react_comment_inner = QWidget(); self._seed_react_comment_inner.setStyleSheet("background: #1a1a1a;")
        self._seed_react_comment_layout = QVBoxLayout(self._seed_react_comment_inner)
        self._seed_react_comment_layout.setSpacing(2); self._seed_react_comment_layout.setContentsMargins(6, 6, 6, 6)
        self._seed_react_comment_layout.addStretch()
        self._seed_react_comment_scroll.setWidget(self._seed_react_comment_inner)
        rp_layout.addWidget(self._seed_react_comment_scroll)

        _cb_line_style = """QCheckBox { color: #cccccc; font-size: 15px; font-family: 'Khmer OS', 'Noto Sans Khmer', 'Leelawadee UI', Arial, sans-serif; background: transparent; spacing: 8px; }
            QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 1px solid #3d3d3d; background: #252525; }
            QCheckBox::indicator:checked { background: #4CAF50; border-color: #4CAF50; }"""

        def _add_comment_line(text):
            cb = QCheckBox(text); cb.setChecked(True); cb.setStyleSheet(_cb_line_style)
            cb.setMinimumHeight(32)
            # Insert before the stretch
            count = self._seed_react_comment_layout.count()
            self._seed_react_comment_layout.insertWidget(count - 1, cb)

        def _paste_comments():
            text = QApplication.clipboard().text().strip()
            if not text: return
            for line in [l.strip() for l in text.splitlines() if l.strip()]:
                _add_comment_line(line)

        def _clear_react_comments():
            while self._seed_react_comment_layout.count() > 1:
                item = self._seed_react_comment_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()

        def _open_add_comments_dialog(parent_widget, on_add_line):
            """Reusable multi-comment input dialog."""
            dlg = QDialog(parent_widget)
            dlg.setWindowTitle("Add Comments")
            dlg.setFixedSize(480, 380)
            dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
            dlg.setStyleSheet("""
                QDialog { background: #1e1e1e; }
                QLabel { color: #cccccc; font-size: 12px; background: transparent; }
                QTextEdit {
                    background: #141414;
                    border: 1px solid #3d3d3d;
                    border-radius: 6px;
                    color: #e0e0e0;
                    font-size: 13px;
                    font-family: 'Khmer OS', 'Noto Sans Khmer', 'Leelawadee UI', Arial, sans-serif;
                    padding: 8px;
                    selection-background-color: #4CAF50;
                }
                QTextEdit:focus { border-color: #4CAF50; }
                QPushButton {
                    border-radius: 5px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 18px;
                    height: 34px;
                }
            """)
            root = QVBoxLayout(dlg)
            root.setContentsMargins(20, 18, 20, 18)
            root.setSpacing(12)

            # Header
            hdr_row = QHBoxLayout(); hdr_row.setSpacing(10)
            ico_lbl = QLabel(); ico_lbl.setPixmap(qta.icon('fa5s.comment-dots', color='#4CAF50').pixmap(20, 20))
            title_lbl = QLabel("Add Comments")
            title_lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; background: transparent;")
            hdr_row.addWidget(ico_lbl); hdr_row.addWidget(title_lbl); hdr_row.addStretch()
            root.addLayout(hdr_row)

            # Hint
            hint = QLabel("One comment per line — each line will be added as a separate entry.")
            hint.setStyleSheet("color: #666666; font-size: 11px; background: transparent;")
            hint.setWordWrap(True)
            root.addWidget(hint)

            # Text area
            te = QTextEdit()
            te.setPlaceholderText("Type your comments here...\nLine 1\nLine 2\nLine 3")
            te.setMinimumHeight(200)
            root.addWidget(te, 1)

            # Counter label
            counter = QLabel("0 comment(s)")
            counter.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
            root.addWidget(counter)

            def _update_counter():
                lines = [l.strip() for l in te.toPlainText().splitlines() if l.strip()]
                counter.setText(f"{len(lines)} comment(s)")
                counter.setStyleSheet(f"color: {'#4CAF50' if lines else '#555555'}; font-size: 11px; background: transparent;")
            te.textChanged.connect(_update_counter)

            # Buttons
            btn_row = QHBoxLayout(); btn_row.setSpacing(8)
            paste_btn = QPushButton(qta.icon('fa5s.clipboard', color='#888888'), "  Paste")
            paste_btn.setStyleSheet("QPushButton { background: #252526; color: #aaaaaa; border: 1px solid #3d3d3d; } QPushButton:hover { border-color: #555555; color: #cccccc; background: #2a2a2a; }")
            paste_btn.clicked.connect(lambda: te.setPlainText(
                (te.toPlainText().rstrip('\n') + '\n' + QApplication.clipboard().text()).lstrip('\n')
            ))
            clear_btn = QPushButton(qta.icon('fa5s.eraser', color='#888888'), "  Clear")
            clear_btn.setStyleSheet("QPushButton { background: #252526; color: #aaaaaa; border: 1px solid #3d3d3d; } QPushButton:hover { border-color: #555555; color: #cccccc; background: #2a2a2a; }")
            clear_btn.clicked.connect(te.clear)
            btn_row.addWidget(paste_btn); btn_row.addWidget(clear_btn); btn_row.addStretch()
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setStyleSheet("QPushButton { background: #252526; color: #aaaaaa; border: 1px solid #3d3d3d; } QPushButton:hover { border-color: #555555; color: #cccccc; background: #2a2a2a; }")
            cancel_btn.clicked.connect(dlg.reject)
            add_btn = QPushButton(qta.icon('fa5s.plus', color='#ffffff'), "  Add")
            add_btn.setStyleSheet("QPushButton { background: #4CAF50; color: #ffffff; border: none; } QPushButton:hover { background: #45a049; } QPushButton:pressed { background: #3d8b40; }")
            add_btn.setDefault(True)
            def _do_add():
                lines = [l.strip() for l in te.toPlainText().splitlines() if l.strip()]
                for line in lines:
                    on_add_line(line)
                dlg.accept()
            add_btn.clicked.connect(_do_add)
            btn_row.addWidget(cancel_btn); btn_row.addWidget(add_btn)
            root.addLayout(btn_row)
            te.setFocus()
            dlg.exec()

        def _show_react_comment_context_menu(pos):
            from PyQt6.QtWidgets import QMenu
            menu = QMenu(self._seed_react_comment_scroll)
            menu.setStyleSheet("""
                QMenu { background: #252526; border: 1px solid #3d3d3d; border-radius: 6px; padding: 4px; color: #cccccc; font-size: 12px; }
                QMenu::item { padding: 7px 20px 7px 12px; border-radius: 4px; }
                QMenu::item:selected { background: #2a2d2e; color: #ffffff; }
                QMenu::item:disabled { color: #555555; }
                QMenu::separator { height: 1px; background: #3d3d3d; margin: 4px 8px; }
            """)
            act_add = menu.addAction(qta.icon('fa5s.plus', color='#4CAF50'), "Add Comment")
            act_paste = menu.addAction(qta.icon('fa5s.clipboard', color='#888888'), "Paste from Clipboard")
            menu.addSeparator()
            act_sel_all = menu.addAction(qta.icon('fa5s.check-square', color='#888888'), "Select All")
            act_desel_all = menu.addAction(qta.icon('fa5s.square', color='#888888'), "Deselect All")
            menu.addSeparator()
            # count real items (exclude stretch)
            item_count = sum(1 for i in range(self._seed_react_comment_layout.count())
                             if self._seed_react_comment_layout.itemAt(i).widget())
            act_del = menu.addAction(qta.icon('fa5s.times', color='#f44336'), "Delete Selected")
            act_clear = menu.addAction(qta.icon('fa5s.trash-alt', color='#f44336'), "Clear All")
            if item_count == 0:
                act_sel_all.setEnabled(False); act_desel_all.setEnabled(False)
                act_del.setEnabled(False); act_clear.setEnabled(False)
            action = menu.exec(self._seed_react_comment_scroll.viewport().mapToGlobal(pos))
            if action == act_add:
                _open_add_comments_dialog(self._seed_react_comment_scroll, _add_comment_line)
            elif action == act_paste:
                _paste_comments()
            elif action == act_sel_all:
                for i in range(self._seed_react_comment_layout.count()):
                    w = self._seed_react_comment_layout.itemAt(i).widget()
                    if isinstance(w, QCheckBox): w.setChecked(True)
            elif action == act_desel_all:
                for i in range(self._seed_react_comment_layout.count()):
                    w = self._seed_react_comment_layout.itemAt(i).widget()
                    if isinstance(w, QCheckBox): w.setChecked(False)
            elif action == act_del:
                to_remove = []
                for i in range(self._seed_react_comment_layout.count()):
                    w = self._seed_react_comment_layout.itemAt(i).widget()
                    if isinstance(w, QCheckBox) and not w.isChecked():
                        to_remove.append(w)
                for w in to_remove:
                    w.setParent(None); w.deleteLater()
            elif action == act_clear:
                _clear_react_comments()

        self._seed_react_comment_scroll.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._seed_react_comment_scroll.customContextMenuRequested.connect(_show_react_comment_context_menu)

        _clip_row = QHBoxLayout(); _clip_row.setSpacing(8)
        _clip_row.addStretch()
        _clip_btn = QPushButton("  Paste from Clipboard"); _clip_btn.setIcon(qta.icon('fa5s.clipboard', color='#888888'))
        _clip_btn.setFixedHeight(30)
        _clip_btn.setStyleSheet("QPushButton { background: transparent; color: #888888; border: 1px solid #3d3d3d; border-radius: 4px; font-size: 11px; padding: 0 12px; } QPushButton:hover { background: #2a2a2a; color: #cccccc; border-color: #555555; }")
        _clear_btn = QPushButton("  Clear"); _clear_btn.setIcon(qta.icon('fa5s.trash-alt', color='#f44336'))
        _clear_btn.setFixedHeight(30)
        _clear_btn.setStyleSheet("QPushButton { background: transparent; color: #f44336; border: 1px solid #3d3d3d; border-radius: 4px; font-size: 11px; padding: 0 12px; } QPushButton:hover { background: rgba(244,67,54,0.1); }")
        _clip_btn.clicked.connect(_paste_comments)
        _clear_btn.clicked.connect(_clear_react_comments)
        _clip_row.addWidget(_clip_btn); _clip_row.addWidget(_clear_btn)
        rp_layout.addLayout(_clip_row)
        rp_layout.addStretch()
        self.seeding_stack.addWidget(react_page)

        # Comment page
        comment_page = QWidget(); comment_page.setStyleSheet("background: transparent;")
        cp_layout = QVBoxLayout(comment_page); cp_layout.setSpacing(14); cp_layout.setContentsMargins(16, 16, 16, 16)
        _curl_lbl = QLabel("Post URL / ID"); _curl_lbl.setStyleSheet(_SECTION_LABEL)
        self.seed_comment_url_input = QLineEdit()
        self.seed_comment_url_input.setPlaceholderText(
            "Paste any Facebook URL or post ID — post, photo, video, reel, group, share link, fb.me/...")
        self.seed_comment_url_input.setStyleSheet(_INPUT_STYLE); self.seed_comment_url_input.setFixedHeight(36)
        # Live URL-type badge
        self._seed_comment_url_badge = QLabel("")
        self._seed_comment_url_badge.setStyleSheet("color: #888888; font-size: 11px; padding: 0 2px;")
        def _update_comment_url_badge(text):
            t = text.strip()
            if not t:
                self._seed_comment_url_badge.setText("")
                return
            _, utype = normalize_facebook_url(t)
            label, color = _URL_TYPE_LABELS.get(utype, ("🔗 URL", "#888888"))
            self._seed_comment_url_badge.setText(f"<span style='color:{color};'>{label}</span>")
        self.seed_comment_url_input.textChanged.connect(_update_comment_url_badge)
        cp_layout.addWidget(_curl_lbl); cp_layout.addWidget(self.seed_comment_url_input)
        cp_layout.addWidget(self._seed_comment_url_badge)

        _ctxt_lbl = QLabel("Comments"); _ctxt_lbl.setStyleSheet(_SECTION_LABEL)
        cp_layout.addWidget(_ctxt_lbl)

        # Comment list scroll area (text + image entries)
        self._seed_comment_scroll = QScrollArea(); self._seed_comment_scroll.setWidgetResizable(True)
        self._seed_comment_scroll.setStyleSheet("""
            QScrollArea { background: #1a1a1a; border: 1px solid #3d3d3d; border-radius: 6px; }
            QScrollArea > QWidget > QWidget { background: #1a1a1a; border-radius: 6px; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: #3d3d3d; border-radius: 3px; }
        """)
        self._seed_comment_scroll.viewport().setStyleSheet("background: #1a1a1a; border-radius: 6px;")
        self._seed_comment_inner = QWidget(); self._seed_comment_inner.setStyleSheet("background: #1a1a1a;")
        self._seed_comment_layout = QVBoxLayout(self._seed_comment_inner)
        self._seed_comment_layout.setSpacing(2); self._seed_comment_layout.setContentsMargins(6, 6, 6, 6)
        self._seed_comment_layout.addStretch()
        self._seed_comment_scroll.setWidget(self._seed_comment_inner)
        cp_layout.addWidget(self._seed_comment_scroll, 1)

        _cb_comment_style = """QCheckBox { color: #cccccc; font-size: 14px; font-family: 'Khmer OS', 'Noto Sans Khmer', 'Leelawadee UI', Arial, sans-serif; background: transparent; spacing: 8px; }
            QCheckBox::indicator { width: 15px; height: 15px; border-radius: 3px; border: 1px solid #3d3d3d; background: #252525; }
            QCheckBox::indicator:checked { background: #4CAF50; border-color: #4CAF50; }"""

        def _add_comment_entry(content, is_image=False):
            row_w = QWidget(); row_w.setStyleSheet("background: transparent;")
            row_l = QHBoxLayout(row_w); row_l.setContentsMargins(2, 2, 2, 2); row_l.setSpacing(8)
            cb = QCheckBox(); cb.setChecked(True)
            cb.setStyleSheet("QCheckBox { background: transparent; } QCheckBox::indicator { width: 15px; height: 15px; border-radius: 3px; border: 1px solid #3d3d3d; background: #252525; } QCheckBox::indicator:checked { background: #4CAF50; border-color: #4CAF50; }")
            row_l.addWidget(cb)
            if is_image:
                img_lbl = QLabel()
                px = QPixmap(content)
                if not px.isNull():
                    img_lbl.setPixmap(px.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    img_lbl.setText(os.path.basename(content))
                    img_lbl.setStyleSheet("color: #FF9800; font-size: 12px; background: transparent;")
                img_lbl.setToolTip(content)
                row_l.addWidget(img_lbl)
                path_lbl = QLabel(os.path.basename(content)); path_lbl.setStyleSheet("color: #888888; font-size: 11px; background: transparent;")
                row_l.addWidget(path_lbl, 1)
                row_w.setProperty("entry_type", "image")
                row_w.setProperty("entry_value", content)
            else:
                txt_lbl = QLabel(content); txt_lbl.setStyleSheet("color: #cccccc; font-size: 14px; font-family: 'Khmer OS','Noto Sans Khmer','Leelawadee UI',Arial,sans-serif; background: transparent;")
                txt_lbl.setWordWrap(True); txt_lbl.setMinimumHeight(28)
                row_l.addWidget(txt_lbl, 1)
                row_w.setProperty("entry_type", "text")
                row_w.setProperty("entry_value", content)
            del_btn = QPushButton(); del_btn.setIcon(qta.icon('fa5s.times', color='#555555'))
            del_btn.setFixedSize(20, 20); del_btn.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { color: #f44336; }")
            del_btn.clicked.connect(lambda: (row_w.setParent(None), row_w.deleteLater()))
            row_l.addWidget(del_btn)
            count = self._seed_comment_layout.count()
            self._seed_comment_layout.insertWidget(count - 1, row_w)

        def _show_comment_context_menu(pos):
            from PyQt6.QtWidgets import QMenu
            menu = QMenu(self._seed_comment_scroll)
            menu.setStyleSheet("""
                QMenu { background: #252526; border: 1px solid #3d3d3d; border-radius: 6px; padding: 4px; color: #cccccc; font-size: 12px; }
                QMenu::item { padding: 7px 20px 7px 12px; border-radius: 4px; }
                QMenu::item:selected { background: #2a2d2e; color: #ffffff; }
                QMenu::item:disabled { color: #555555; }
                QMenu::separator { height: 1px; background: #3d3d3d; margin: 4px 8px; }
            """)
            act_add_text = menu.addAction(qta.icon('fa5s.comment', color='#4CAF50'), "Add Text Comment")
            act_add_img = menu.addAction(qta.icon('fa5s.image', color='#4CAF50'), "Add Image")
            act_paste = menu.addAction(qta.icon('fa5s.clipboard', color='#888888'), "Paste from Clipboard")
            menu.addSeparator()
            act_sel_all = menu.addAction(qta.icon('fa5s.check-square', color='#888888'), "Select All")
            act_desel_all = menu.addAction(qta.icon('fa5s.square', color='#888888'), "Deselect All")
            menu.addSeparator()
            act_del = menu.addAction(qta.icon('fa5s.times', color='#f44336'), "Delete Unchecked")
            act_clear = menu.addAction(qta.icon('fa5s.trash-alt', color='#f44336'), "Clear All")
            # count real items
            item_count = sum(1 for i in range(self._seed_comment_layout.count())
                             if self._seed_comment_layout.itemAt(i).widget())
            if item_count == 0:
                act_sel_all.setEnabled(False); act_desel_all.setEnabled(False)
                act_del.setEnabled(False); act_clear.setEnabled(False)
            action = menu.exec(self._seed_comment_scroll.viewport().mapToGlobal(pos))
            if action == act_add_text:
                _open_add_comments_dialog(self._seed_comment_scroll, lambda line: _add_comment_entry(line, is_image=False))
            elif action == act_add_img:
                from PyQt6.QtWidgets import QFileDialog
                files, _ = QFileDialog.getOpenFileNames(self._seed_comment_scroll, "Select Images", "", "Images (*.png *.jpg *.jpeg *.gif *.webp)")
                for f in files:
                    _add_comment_entry(f, is_image=True)
            elif action == act_paste:
                text = QApplication.clipboard().text().strip()
                if text:
                    for line in [l.strip() for l in text.splitlines() if l.strip()]:
                        _add_comment_entry(line, is_image=False)
            elif action == act_sel_all:
                for i in range(self._seed_comment_layout.count()):
                    w = self._seed_comment_layout.itemAt(i).widget()
                    if w:
                        cb = w.findChild(QCheckBox)
                        if cb: cb.setChecked(True)
            elif action == act_desel_all:
                for i in range(self._seed_comment_layout.count()):
                    w = self._seed_comment_layout.itemAt(i).widget()
                    if w:
                        cb = w.findChild(QCheckBox)
                        if cb: cb.setChecked(False)
            elif action == act_del:
                to_remove = []
                for i in range(self._seed_comment_layout.count()):
                    w = self._seed_comment_layout.itemAt(i).widget()
                    if w:
                        cb = w.findChild(QCheckBox)
                        if cb and not cb.isChecked():
                            to_remove.append(w)
                for w in to_remove:
                    w.setParent(None); w.deleteLater()
            elif action == act_clear:
                while self._seed_comment_layout.count() > 1:
                    item = self._seed_comment_layout.takeAt(0)
                    if item.widget(): item.widget().deleteLater()

        self._seed_comment_scroll.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._seed_comment_scroll.customContextMenuRequested.connect(_show_comment_context_menu)

        # Buttons row
        _cmt_btn_row = QHBoxLayout(); _cmt_btn_row.setSpacing(8); _cmt_btn_row.addStretch()
        _paste_txt_btn = QPushButton("  Paste Text"); _paste_txt_btn.setIcon(qta.icon('fa5s.clipboard', color='#888888'))
        _paste_txt_btn.setFixedHeight(30)
        _paste_txt_btn.setStyleSheet("QPushButton { background: transparent; color: #888888; border: 1px solid #3d3d3d; border-radius: 4px; font-size: 11px; padding: 0 12px; } QPushButton:hover { background: #2a2a2a; color: #cccccc; border-color: #555555; }")
        _add_img_btn = QPushButton("  Add Image"); _add_img_btn.setIcon(qta.icon('fa5s.image', color='#888888'))
        _add_img_btn.setFixedHeight(30)
        _add_img_btn.setStyleSheet("QPushButton { background: transparent; color: #888888; border: 1px solid #3d3d3d; border-radius: 4px; font-size: 11px; padding: 0 12px; } QPushButton:hover { background: #2a2a2a; color: #cccccc; border-color: #555555; }")
        _clear_cmt_btn = QPushButton("  Clear"); _clear_cmt_btn.setIcon(qta.icon('fa5s.trash-alt', color='#f44336'))
        _clear_cmt_btn.setFixedHeight(30)
        _clear_cmt_btn.setStyleSheet("QPushButton { background: transparent; color: #f44336; border: 1px solid #3d3d3d; border-radius: 4px; font-size: 11px; padding: 0 12px; } QPushButton:hover { background: rgba(244,67,54,0.1); }")

        def _paste_text():
            text = QApplication.clipboard().text().strip()
            if not text: return
            for line in [l.strip() for l in text.splitlines() if l.strip()]:
                _add_comment_entry(line, is_image=False)

        def _add_image():
            from PyQt6.QtWidgets import QFileDialog
            files, _ = QFileDialog.getOpenFileNames(comment_page, "Select Images", "", "Images (*.png *.jpg *.jpeg *.gif *.webp)")
            for f in files:
                _add_comment_entry(f, is_image=True)

        def _clear_comments():
            while self._seed_comment_layout.count() > 1:
                item = self._seed_comment_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()

        _paste_txt_btn.clicked.connect(_paste_text)
        _add_img_btn.clicked.connect(_add_image)
        _clear_cmt_btn.clicked.connect(_clear_comments)
        _cmt_btn_row.addWidget(_paste_txt_btn); _cmt_btn_row.addWidget(_add_img_btn); _cmt_btn_row.addWidget(_clear_cmt_btn)
        cp_layout.addLayout(_cmt_btn_row)

        cp_layout.addStretch()
        self.seeding_stack.addWidget(comment_page)
        center_layout.addWidget(self.seeding_stack, 1)
        main_layout.addWidget(center_panel, 42)

        # ── RIGHT PANEL: Devices + Settings (30%) ─────────────────────────
        right_panel = QFrame()
        right_panel.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; }")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(0)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_toolbar = QFrame(); right_toolbar.setFixedHeight(52); right_toolbar.setStyleSheet(_TOOLBAR_STYLE)
        rt_layout = QHBoxLayout(right_toolbar); rt_layout.setContentsMargins(14, 0, 10, 0); rt_layout.setSpacing(8)
        rt_title = QLabel("Devices"); rt_title.setStyleSheet(_TITLE_STYLE)
        self.seed_device_count_label = QLabel("0 device(s)")
        self.seed_device_count_label.setStyleSheet("QLabel { background: transparent; color: #4CAF50; font-size: 12px; font-weight: 500; padding: 0; border: none; }")
        rt_layout.addWidget(rt_title); rt_layout.addWidget(self.seed_device_count_label); rt_layout.addStretch()
        refresh_dev_btn = QPushButton(); refresh_dev_btn.setIcon(qta.icon('fa5s.sync-alt', color='#888888'))
        refresh_dev_btn.setFixedSize(26, 26); refresh_dev_btn.setToolTip("Refresh devices")
        refresh_dev_btn.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { background: #2a2a2a; border-radius: 4px; }")
        refresh_dev_btn.clicked.connect(self._refresh_all_devices)
        adv_settings_btn = QPushButton(qta.icon('fa5s.sliders-h', color='#888888'), "  Settings")
        adv_settings_btn.setFixedHeight(28)
        adv_settings_btn.setStyleSheet("QPushButton { background: #252526; color: #888888; border: 1px solid #3d3d3d; border-radius: 5px; font-size: 11px; font-weight: 600; padding: 0 10px; } QPushButton:hover { border-color: #4CAF50; color: #cccccc; background: #2a2a2a; }")
        adv_settings_btn.clicked.connect(lambda: self._open_seeding_advanced())
        rt_layout.addWidget(adv_settings_btn)
        rt_layout.addWidget(refresh_dev_btn)
        right_layout.addWidget(right_toolbar)

        self.seed_device_table = QTableWidget()
        self.seed_device_table.setColumnCount(3)
        self.seed_device_table.setHorizontalHeaderLabels(["Device", "Proxy", "Changer"])
        self.seed_device_table.setStyleSheet(_TABLE_STYLE)
        self.seed_device_table.verticalHeader().setVisible(False)
        self.seed_device_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.seed_device_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.seed_device_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.seed_device_table.setShowGrid(False)
        self.seed_device_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.seed_device_table.verticalHeader().setDefaultSectionSize(36)
        dev_hdr = self.seed_device_table.horizontalHeader()
        dev_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        dev_hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        dev_hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        dev_hdr.setStretchLastSection(False)
        self.seed_device_table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        right_layout.addWidget(self.seed_device_table)

        # Settings stored as plain attributes — no hidden widgets needed
        self._seed_settings = {
            'delay_min': 3,
            'delay_max': 8,
            'repeat': 1,
            'open_app': True,
            'close_app': True,
            'skip_error': True,
            'auto_restore': False,  # Auto restore session before seeding
        }
        # Compatibility shims so existing code that calls .value() / .isChecked() still works
        class _IntVal:
            def __init__(self, d, k): self._d = d; self._k = k
            def value(self): return self._d[self._k]
            def setValue(self, v): self._d[self._k] = v
        class _BoolVal:
            def __init__(self, d, k): self._d = d; self._k = k
            def isChecked(self): return self._d[self._k]
            def setChecked(self, v): self._d[self._k] = bool(v)
        self.seed_delay_min   = _IntVal(self._seed_settings, 'delay_min')
        self.seed_delay_max   = _IntVal(self._seed_settings, 'delay_max')
        self.seed_repeat_spin = _IntVal(self._seed_settings, 'repeat')
        self.seed_open_app_cb  = _BoolVal(self._seed_settings, 'open_app')
        self.seed_close_app_cb = _BoolVal(self._seed_settings, 'close_app')
        self.seed_skip_error_cb = _BoolVal(self._seed_settings, 'skip_error')
        self.seed_auto_restore_cb = _BoolVal(self._seed_settings, 'auto_restore')

        def _open_seeding_advanced():
            dlg = QDialog(self)
            dlg.setWindowTitle("Seeding Settings")
            dlg.setFixedSize(420, 300)
            dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
            dlg.setStyleSheet("""
                QDialog { background: #1e1e1e; }
                QLabel { color: #cccccc; font-size: 12px; background: transparent; }
                QSpinBox { background: #252525; color: #cccccc; border: 1px solid #3d3d3d; border-radius: 5px; padding: 4px 8px; font-size: 12px; }
                QSpinBox:focus { border-color: #4CAF50; }
                QSpinBox::up-button, QSpinBox::down-button { width: 16px; background: #2d2d2d; border: none; }
                QCheckBox { color: #cccccc; font-size: 12px; spacing: 8px; }
                QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 1px solid #3d3d3d; background: #252525; }
                QCheckBox::indicator:checked { background: #4CAF50; border-color: #4CAF50; }
                QPushButton { border-radius: 5px; font-size: 12px; font-weight: 600; padding: 0 18px; height: 34px; }
            """)
            root = QVBoxLayout(dlg)
            root.setContentsMargins(24, 20, 24, 20)
            root.setSpacing(16)

            # Header
            hdr = QHBoxLayout(); hdr.setSpacing(10)
            hdr_ico = QLabel(); hdr_ico.setPixmap(qta.icon('fa5s.sliders-h', color='#4CAF50').pixmap(18, 18))
            hdr_lbl = QLabel("Seeding Settings")
            hdr_lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; background: transparent;")
            hdr.addWidget(hdr_ico); hdr.addWidget(hdr_lbl); hdr.addStretch()
            root.addLayout(hdr)

            # Divider
            div = QFrame(); div.setFixedHeight(1); div.setStyleSheet("background: #2a2a2a;")
            root.addWidget(div)

            # Delay row
            delay_row = QHBoxLayout(); delay_row.setSpacing(8)
            delay_row.addWidget(QLabel("Delay between actions (s)"), 1)
            # Proxy spinboxes — bind to the real self.seed_delay_min/max
            _dmin = QSpinBox(); _dmin.setRange(1, 300); _dmin.setValue(self.seed_delay_min.value()); _dmin.setFixedWidth(64)
            _dsep = QLabel("–"); _dsep.setStyleSheet("color: #555555; background: transparent;")
            _dmax = QSpinBox(); _dmax.setRange(1, 300); _dmax.setValue(self.seed_delay_max.value()); _dmax.setFixedWidth(64)
            delay_row.addWidget(_dmin); delay_row.addWidget(_dsep); delay_row.addWidget(_dmax)
            root.addLayout(delay_row)

            # Repeat row
            rep_row = QHBoxLayout(); rep_row.setSpacing(8)
            rep_row.addWidget(QLabel("Repeat per account"), 1)
            _rep = QSpinBox(); _rep.setRange(1, 50); _rep.setValue(self.seed_repeat_spin.value()); _rep.setFixedWidth(64)
            rep_row.addWidget(_rep)
            root.addLayout(rep_row)

            # Checkboxes
            _cb_open  = QCheckBox("Open Facebook before action");  _cb_open.setChecked(self.seed_open_app_cb.isChecked())
            _cb_close = QCheckBox("Close Facebook after action");   _cb_close.setChecked(self.seed_close_app_cb.isChecked())
            _cb_skip  = QCheckBox("Skip device on error");          _cb_skip.setChecked(self.seed_skip_error_cb.isChecked())
            _cb_restore = QCheckBox("🔄 Auto restore session before seeding")
            _cb_restore.setChecked(self.seed_auto_restore_cb.isChecked())
            _cb_restore.setToolTip(
                "Automatically restore each account's session on the device before seeding.\n"
                "Accounts are taken from the Accounts panel (left) and distributed\n"
                "across selected devices. No manual Login tab needed."
            )
            for cb in [_cb_open, _cb_close, _cb_skip, _cb_restore]:
                root.addWidget(cb)

            root.addStretch()

            # Buttons
            btn_row = QHBoxLayout(); btn_row.setSpacing(8); btn_row.addStretch()
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setStyleSheet("QPushButton { background: #252526; color: #aaaaaa; border: 1px solid #3d3d3d; } QPushButton:hover { border-color: #555555; color: #cccccc; }")
            cancel_btn.clicked.connect(dlg.reject)
            save_btn = QPushButton(qta.icon('fa5s.check', color='#ffffff'), "  Save")
            save_btn.setStyleSheet("QPushButton { background: #4CAF50; color: #ffffff; border: none; } QPushButton:hover { background: #45a049; } QPushButton:pressed { background: #3d8b40; }")
            save_btn.setDefault(True)
            def _save():
                self.seed_delay_min.setValue(_dmin.value())
                self.seed_delay_max.setValue(_dmax.value())
                self.seed_repeat_spin.setValue(_rep.value())
                self.seed_open_app_cb.setChecked(_cb_open.isChecked())
                self.seed_close_app_cb.setChecked(_cb_close.isChecked())
                self.seed_skip_error_cb.setChecked(_cb_skip.isChecked())
                self.seed_auto_restore_cb.setChecked(_cb_restore.isChecked())
                dlg.accept()
            save_btn.clicked.connect(_save)
            btn_row.addWidget(cancel_btn); btn_row.addWidget(save_btn)
            root.addLayout(btn_row)
            dlg.exec()

        self._open_seeding_advanced = _open_seeding_advanced

        # Action bar at bottom of right panel
        right_action_bar = QFrame(); right_action_bar.setFixedHeight(56)
        right_action_bar.setStyleSheet("QFrame { background: #1e1e1e; border: none; border-top: 1px solid #2a2a2a; }")
        ra_layout = QHBoxLayout(right_action_bar); ra_layout.setContentsMargins(14, 0, 14, 0); ra_layout.setSpacing(8)
        self.seed_start_btn = QPushButton("  Start Seeding"); self.seed_start_btn.setIcon(qta.icon('fa5s.play', color='#ffffff'))
        self.seed_start_btn.setFixedHeight(36); self.seed_start_btn.setStyleSheet(_BTN_GREEN)
        self.seed_stop_btn = QPushButton("  Stop"); self.seed_stop_btn.setIcon(qta.icon('fa5s.stop', color='#f44336'))
        self.seed_stop_btn.setFixedHeight(36); self.seed_stop_btn.setEnabled(False)
        self.seed_stop_btn.setStyleSheet("QPushButton { background: transparent; color: #f44336; border: 1px solid #f44336; border-radius: 5px; padding: 6px 14px; font-size: 12px; font-weight: 600; } QPushButton:hover { background: rgba(244,67,54,0.1); } QPushButton:disabled { color: #3d3d3d; border-color: #2a2a2a; }")
        self.seed_start_btn.clicked.connect(self._start_seeding)
        self.seed_stop_btn.clicked.connect(self._stop_seeding)
        ra_layout.addStretch()
        ra_layout.addWidget(self.seed_stop_btn); ra_layout.addWidget(self.seed_start_btn)
        right_layout.addWidget(right_action_bar)

        main_layout.addWidget(right_panel, 30)

        return tab


    def _load_seeding_accounts(self):
        """Load accounts into the seeding account table — I/O in background."""
        import threading as _t

        def _gather():
            rows = []
            backup_path = os.path.join(_PROJECT_ROOT, "account_backup")
            if os.path.exists(backup_path):
                for folder in sorted(os.listdir(backup_path)):
                    jp = os.path.join(backup_path, folder, "account_info.json")
                    if not os.path.exists(jp): continue
                    try:
                        with open(jp, 'r', encoding='utf-8') as f: d = json.load(f)
                        uid = d.get('account_uid', d.get('uid', folder.split('_')[0]))
                        name = d.get('full_name', (d.get('first_name','') + ' ' + d.get('last_name','')).strip()) or '—'
                        rows.append((uid, name))
                    except: pass
            from PyQt6.QtCore import QMetaObject, Qt
            self._seeding_accounts_pending = rows
            QMetaObject.invokeMethod(self, "_apply_seeding_accounts", Qt.ConnectionType.QueuedConnection)

        _t.Thread(target=_gather, daemon=True).start()

    @pyqtSlot()
    def _apply_seeding_accounts(self):
        """Apply loaded seeding accounts to table on main thread."""
        rows = getattr(self, '_seeding_accounts_pending', [])
        try:
            self.seeding_account_table.setRowCount(0)
            for count, (uid, name) in enumerate(rows, 1):
                row = self.seeding_account_table.rowCount()
                self.seeding_account_table.insertRow(row)
                self.seeding_account_table.setRowHeight(row, 36)
                n_item = QTableWidgetItem(str(count)); n_item.setForeground(QColor("#555555")); n_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                u_item = QTableWidgetItem(uid); u_item.setForeground(QColor("#4CAF50"))
                nm_item = QTableWidgetItem(name); nm_item.setForeground(QColor("#cccccc"))
                s_item = QTableWidgetItem("Ready"); s_item.setForeground(QColor("#555555"))
                for col, item in enumerate([n_item, u_item, nm_item, s_item]):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self.seeding_account_table.setItem(row, col, item)
            self.auto_seed_account_badge.setText(f"{len(rows)} accounts")
            self._seed_stat_total.setText(f"Total: {len(rows)}")
        except Exception as e:
            print(f"Error applying seeding accounts: {e}")


    def _seed_select_accounts(self):
        """Open account picker dialog to add accounts to seeding queue - styled like login dialog"""
        backup_path = os.path.join(_PROJECT_ROOT, "account_backup")
        if not os.path.exists(backup_path):
            QMessageBox.warning(self, "No Accounts", "No account_backup folder found.")
            return

        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        dialog.setFixedSize(1100, 620)
        dialog.setStyleSheet("QDialog { background: #1e1e1e; border: 1px solid #3d3d3d; }")
        
        root = QVBoxLayout(dialog); root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame(); hdr.setObjectName("salHdr"); hdr.setFixedHeight(52)
        hdr.setStyleSheet("QFrame#salHdr { background: #252526; border: none; border-bottom: 1px solid #2a2a2a; }")
        hdr_l = QHBoxLayout(hdr); hdr_l.setContentsMargins(20, 0, 12, 0); hdr_l.setSpacing(10)
        ico = QLabel(); ico.setPixmap(qta.icon('fa5s.users', color='#4CAF50').pixmap(14, 14))
        ico.setStyleSheet("background: transparent;"); hdr_l.addWidget(ico)
        ttl = QLabel("Select Accounts for Seeding")
        ttl.setStyleSheet("color: #cccccc; font-size: 13px; font-weight: bold; background: transparent;")
        hdr_l.addWidget(ttl); hdr_l.addStretch()
        x_btn = QPushButton(); x_btn.setFixedSize(32, 32)
        x_btn.setIcon(qta.icon('fa5s.times', color='#888888')); x_btn.setIconSize(QSize(12, 12))
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
        _combo_s = """QComboBox { background: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 4px;
            padding: 0 10px; color: #cccccc; font-size: 12px; min-width: 120px; height: 30px; }
            QComboBox:hover { border-color: #4CAF50; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow { image: none; border-left: 4px solid transparent;
                border-right: 4px solid transparent; border-top: 5px solid #888; margin-right: 6px; }
            QComboBox QAbstractItemView { background: #252526; border: 1px solid #3d3d3d;
                color: #cccccc; selection-background-color: #4CAF50; selection-color: #fff; }"""
        _search_s = """QLineEdit { background: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 4px;
            padding: 0 10px; color: #cccccc; font-size: 12px; height: 30px; min-width: 220px; }
            QLineEdit:focus { border-color: #4CAF50; }"""
        _lbl_s = "color: #666666; font-size: 11px; font-weight: bold; background: transparent;"

        fbar = QWidget(); fbar.setStyleSheet("background: #1e1e1e;")
        fbar_l = QHBoxLayout(fbar); fbar_l.setContentsMargins(20, 12, 20, 8); fbar_l.setSpacing(10)
        cl = QLabel("Category:"); cl.setStyleSheet(_lbl_s); fbar_l.addWidget(cl)
        category_filter = SafeComboBox(); category_filter.addItems(["All", "Email", "Phone", "---"])
        # Add custom categories
        for cat in self.load_custom_categories(): category_filter.addItem(cat)
        category_filter.setStyleSheet(_combo_s); fbar_l.addWidget(category_filter)
        fbar_l.addSpacing(8)
        sl = QLabel("Status:"); sl.setStyleSheet(_lbl_s); fbar_l.addWidget(sl)
        status_filter = SafeComboBox(); status_filter.addItems(["All", "Active", "Suspended"])
        status_filter.setStyleSheet(_combo_s); fbar_l.addWidget(status_filter)
        fbar_l.addStretch()
        sch_l = QLabel("Search:"); sch_l.setStyleSheet(_lbl_s); fbar_l.addWidget(sch_l)
        search_input = QLineEdit(); search_input.setPlaceholderText("Search by name, email, phone...")
        search_input.setStyleSheet(_search_s); fbar_l.addWidget(search_input)
        root.addWidget(fbar)
        
        # Table
        _tbl_s = """QTableWidget { background: #1e1e1e; border: none; gridline-color: #2a2a2a;
            color: #cccccc; font-size: 12px; outline: none; }
            QTableWidget::item { padding: 0 10px; border: none; }
            QTableWidget::item:hover { background: transparent; }
            QTableWidget::item:selected { background: #2a4a2a; color: #ffffff; }
            QTableWidget::item:selected:hover { background: #2a4a2a; }
            QHeaderView::section { background: #252526; color: #4CAF50; font-size: 11px; font-weight: bold;
                letter-spacing: 0.5px; padding: 0 10px; height: 34px;
                border: none; border-bottom: 2px solid #4CAF50; border-right: 1px solid #2a2a2a; }"""
        _cb_style = """QCheckBox { background: transparent; }
            QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid #3d3d3d;
                border-radius: 3px; background: #2d2d2d; }
            QCheckBox::indicator:hover { border-color: #4CAF50; }
            QCheckBox::indicator:checked { background: #4CAF50; border-color: #4CAF50; }"""

        pick_table = QTableWidget(); pick_table.setColumnCount(7)
        pick_table.setHorizontalHeaderLabels(["", "Name", "UID", "Email/Phone", "Status", "Created", "Category"])
        pick_table.setStyleSheet(_tbl_s)
        pick_table.verticalHeader().setVisible(False)
        pick_table.verticalHeader().setDefaultSectionSize(38)
        pick_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        pick_table.setSelectionMode(QTableWidget.SelectionMode.MultiSelection)
        pick_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        pick_table.setShowGrid(True)
        hdr_view = pick_table.horizontalHeader()
        hdr_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed); pick_table.setColumnWidth(0, 50)
        hdr_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr_view.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        hdr_view.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        hdr_view.setHighlightSections(False)

        all_accounts = []
        for folder in sorted(os.listdir(backup_path)):
            jp = os.path.join(backup_path, folder, "account_info.json")
            if not os.path.exists(jp): continue
            try:
                with open(jp, 'r', encoding='utf-8') as f: all_accounts.append(json.load(f))
            except: pass

        def populate_table(accounts):
            pick_table.setRowCount(0)
            for acc in accounts:
                row = pick_table.rowCount(); pick_table.insertRow(row)
                cb = QCheckBox(); cb.setStyleSheet(_cb_style)
                def _make_handler(r):
                    def _h(checked):
                        pick_table.blockSignals(True)
                        if checked: pick_table.selectRow(r)
                        else:
                            pick_table.clearSelection()
                            for i in range(pick_table.rowCount()):
                                if i != r:
                                    w = pick_table.cellWidget(i, 0)
                                    if w:
                                        c = w.findChild(QCheckBox)
                                        if c and c.isChecked(): pick_table.selectRow(i)
                        pick_table.blockSignals(False)
                    return _h
                cb.stateChanged.connect(_make_handler(row))
                cw = QWidget(); cw.setStyleSheet("background: transparent;")
                cwl = QHBoxLayout(cw); cwl.addWidget(cb); cwl.setAlignment(Qt.AlignmentFlag.AlignCenter); cwl.setContentsMargins(0,0,0,0)
                pick_table.setCellWidget(row, 0, cw)
                name = acc.get('full_name', (acc.get('first_name','') + ' ' + acc.get('last_name','')).strip()) or 'N/A'
                uid = acc.get('account_uid', acc.get('uid', '—'))
                email_phone = acc.get('email') or acc.get('phone') or '—'
                status = acc.get('status', 'Active')
                created = acc.get('created_at', acc.get('created_date', '—'))
                category = acc.get('category', '—')
                pick_table.setItem(row, 1, QTableWidgetItem(name))
                pick_table.setItem(row, 2, QTableWidgetItem(uid))
                pick_table.setItem(row, 3, QTableWidgetItem(email_phone))
                status_item = QTableWidgetItem(status)
                status_item.setForeground(QColor("#4CAF50") if status.lower() == "active" else QColor("#888888"))
                pick_table.setItem(row, 4, status_item)
                pick_table.setItem(row, 5, QTableWidgetItem(created))
                cat_item = QTableWidgetItem(category)
                cat_item.setForeground(QColor("#4CAF50") if category != "—" else QColor("#888888"))
                pick_table.setItem(row, 6, cat_item)
                for c in [1,2,3,4,5,6]: pick_table.item(row, c).setData(Qt.ItemDataRole.UserRole, acc)

        def _sync_checkboxes_to_selection():
            """Sync checkboxes when rows are selected via drag or click"""
            selected_rows = {idx.row() for idx in pick_table.selectionModel().selectedRows()}
            for i in range(pick_table.rowCount()):
                w = pick_table.cellWidget(i, 0)
                if w:
                    cb = w.findChild(QCheckBox)
                    if cb:
                        cb.blockSignals(True)
                        cb.setChecked(i in selected_rows)
                        cb.blockSignals(False)
            update_count()

        pick_table.itemSelectionChanged.connect(_sync_checkboxes_to_selection)

        populate_table(all_accounts)

        def apply_filters():
            cat = category_filter.currentText()
            stat = status_filter.currentText()
            search = search_input.text().lower()
            filtered = []
            for acc in all_accounts:
                if cat not in ("All", "---"):
                    if cat == "Email":
                        if not acc.get('email'): continue
                    elif cat == "Phone":
                        if not acc.get('phone'): continue
                    else:
                        # Custom category
                        if acc.get('category', '') != cat: continue
                if stat != "All" and acc.get('status', 'Active') != stat: continue
                if search:
                    name = acc.get('full_name', '').lower()
                    email = acc.get('email', '').lower()
                    phone = acc.get('phone', '').lower()
                    if search not in name and search not in email and search not in phone: continue
                filtered.append(acc)
            populate_table(filtered)

        category_filter.currentTextChanged.connect(lambda: apply_filters())
        status_filter.currentTextChanged.connect(lambda: apply_filters())
        search_input.textChanged.connect(lambda: apply_filters())

        root.addWidget(pick_table, 1)

        # Footer
        ftr = QFrame(); ftr.setFixedHeight(60)
        ftr.setStyleSheet("QFrame { background: #252526; border: none; border-top: 1px solid #2a2a2a; }")
        ftr_l = QHBoxLayout(ftr); ftr_l.setContentsMargins(20, 0, 20, 0); ftr_l.setSpacing(10)
        sel_count = QLabel("0 selected"); sel_count.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
        ftr_l.addWidget(sel_count); ftr_l.addStretch()

        def update_count():
            count = 0
            for i in range(pick_table.rowCount()):
                w = pick_table.cellWidget(i, 0)
                if w:
                    cb = w.findChild(QCheckBox)
                    if cb and cb.isChecked():
                        count += 1
            sel_count.setText(f"{count} selected")

        def _sync_checkboxes_to_selection():
            selected_rows = {idx.row() for idx in pick_table.selectionModel().selectedRows()}
            for i in range(pick_table.rowCount()):
                w = pick_table.cellWidget(i, 0)
                if w:
                    cb = w.findChild(QCheckBox)
                    if cb:
                        cb.blockSignals(True)
                        cb.setChecked(i in selected_rows)
                        cb.blockSignals(False)
            update_count()

        pick_table.itemSelectionChanged.connect(_sync_checkboxes_to_selection)
        for r in range(pick_table.rowCount()):
            w = pick_table.cellWidget(r, 0)
            if w:
                cb = w.findChild(QCheckBox)
                if cb: cb.stateChanged.connect(update_count)

        cancel_btn = QPushButton("Cancel"); cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet("QPushButton { background: transparent; color: #888; border: 1px solid #3d3d3d; border-radius: 4px; font-size: 12px; padding: 0 20px; } QPushButton:hover { background: #2a2a2a; color: #ccc; }")
        cancel_btn.clicked.connect(dialog.reject); ftr_l.addWidget(cancel_btn)

        add_btn = QPushButton("  Add Selected"); add_btn.setIcon(qta.icon('fa5s.plus', color='#fff'))
        add_btn.setFixedHeight(36)
        add_btn.setStyleSheet("QPushButton { background: #4CAF50; color: #fff; border: none; border-radius: 4px; font-size: 12px; font-weight: bold; padding: 0 20px; } QPushButton:hover { background: #45a049; } QPushButton:pressed { background: #3d8b40; }")
        ftr_l.addWidget(add_btn)
        root.addWidget(ftr)

        def _do_add():
            added = 0
            for r in range(pick_table.rowCount()):
                w = pick_table.cellWidget(r, 0)
                if w:
                    cb = w.findChild(QCheckBox)
                    if cb and cb.isChecked():
                        uid = pick_table.item(r, 2).text()
                        existing = [self.seeding_account_table.item(i, 1).text()
                                    for i in range(self.seeding_account_table.rowCount())
                                    if self.seeding_account_table.item(i, 1)]
                        if uid in existing: continue
                        row = self.seeding_account_table.rowCount()
                        self.seeding_account_table.insertRow(row)
                        self.seeding_account_table.setRowHeight(row, 36)
                        name = pick_table.item(r, 1).text()
                        n_item = QTableWidgetItem(str(row + 1)); n_item.setForeground(QColor("#555555")); n_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        u_item = QTableWidgetItem(uid); u_item.setForeground(QColor("#4CAF50"))
                        nm_item = QTableWidgetItem(name); nm_item.setForeground(QColor("#cccccc"))
                        s_item = QTableWidgetItem("Ready"); s_item.setForeground(QColor("#555555"))
                        for col, item in enumerate([n_item, u_item, nm_item, s_item]):
                            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                            self.seeding_account_table.setItem(row, col, item)
                        added += 1
            count = self.seeding_account_table.rowCount()
            self.auto_seed_account_badge.setText(f"{count} accounts")
            self._seed_stat_total.setText(f"Total: {count}")
            if added > 0:
                dialog.accept()
            else:
                QMessageBox.information(dialog, "No New Accounts", "All selected accounts are already in the queue.")

        add_btn.clicked.connect(_do_add)
        dialog.exec()


    def _seed_clear_accounts(self):
        """Clear all accounts from seeding queue"""
        if self.seeding_account_table.rowCount() == 0:
            return
        reply = QMessageBox.question(self, "Clear Accounts", "Remove all accounts from the seeding queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.seeding_account_table.setRowCount(0)
            self.auto_seed_account_badge.setText("0 accounts")
            self._seed_stat_total.setText("Total: 0")


    def _load_seeding_devices(self):
        """Load connected devices into the seeding device table"""
        import threading, tempfile
        
        # Show loading message
        if hasattr(self, 'seed_device_count_label'):
            self.seed_device_count_label.setText("Scanning...")
        
        def _scan():
            """Background thread: scan devices and gather data"""
            try:
                # Load caches
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
                result = safe_subprocess_run([self.adb_path, "devices"], capture_output=True, text=True, timeout=10)
                
                devices = []
                for line in result.stdout.strip().split('\n')[1:]:
                    if '\t' in line:
                        device_id, status = line.split('\t')
                        if status.strip() == 'device':
                            device_id = device_id.strip()
                            proxy = proxy_cache.get(device_id, '—')
                            spoof = spoof_cache.get(device_id, '—')
                            devices.append((device_id, proxy, spoof))

                # Emit signal with device data
                self._seed_devices_signal.emit(devices)
                
            except Exception as e:
                print(f"Error scanning seeding devices: {e}")
                self._seed_devices_signal.emit([])  # Empty list on error
        
        # Start background thread
        threading.Thread(target=_scan, daemon=True).start()
    
    
    def _apply_seed_devices(self, devices):
        """Apply device list to seeding table (runs on main thread via signal)"""
        try:
            if not hasattr(self, 'seed_device_table'):
                return
            
            # Clear table
            self.seed_device_table.setRowCount(0)
            self.seed_device_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            
            # Populate table
            count = 0
            for device_id, proxy, spoof in devices:
                count += 1
                row = self.seed_device_table.rowCount()
                self.seed_device_table.insertRow(row)
                self.seed_device_table.setRowHeight(row, 36)
                
                d_item = QTableWidgetItem(f"{count}. {device_id}")
                d_item.setForeground(QColor("#4CAF50"))
                p_item = QTableWidgetItem(proxy)
                p_item.setForeground(QColor("#FF9800") if proxy != '—' else QColor("#555555"))
                s_item = QTableWidgetItem(spoof)
                s_item.setForeground(QColor("#FF9800") if spoof != '—' else QColor("#555555"))
                
                for col, item in enumerate([d_item, p_item, s_item]):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self.seed_device_table.setItem(row, col, item)
            
            # Update count label
            if hasattr(self, 'seed_device_count_label'):
                self.seed_device_count_label.setText(f"{count} device(s)")
            
            # Switch col 0 to ResizeToContents when data exists so full ID shows, else keep Stretch
            dev_hdr = self.seed_device_table.horizontalHeader()
            if count > 0:
                dev_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            else:
                dev_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
                
        except Exception as e:
            print(f"Error applying seeding devices: {e}")


    def _start_seeding(self):
        """Start seeding operation"""
        import threading, random, time
        mode = "react" if self.seeding_stack.currentIndex() == 0 else "comment"
        raw_url = self.seed_post_url_input.text().strip() if mode == "react" else self.seed_comment_url_input.text().strip()
        if not raw_url:
            QMessageBox.warning(self, "Missing URL", "Please enter a Post URL or ID.")
            return

        # Normalize URL — supports all Facebook link formats
        url, url_type = normalize_facebook_url(raw_url)
        type_label = _URL_TYPE_LABELS.get(url_type, ("URL", "#888888"))[0]

        # ── Auto-restore mode: account-centric ───────────────────────────
        auto_restore = self.seed_auto_restore_cb.isChecked()

        if auto_restore:
            # Collect selected accounts from the left panel
            acc_rows = self.seeding_account_table.selectionModel().selectedRows()
            if not acc_rows:
                # If nothing selected, use all accounts
                acc_rows = [self.seeding_account_table.model().index(r, 0)
                            for r in range(self.seeding_account_table.rowCount())]
            if not acc_rows:
                QMessageBox.warning(self, "No Accounts", "Add accounts to the Accounts panel first.")
                return

            # Collect selected devices as the pool
            dev_rows = self.seed_device_table.selectionModel().selectedRows()
            if not dev_rows:
                QMessageBox.warning(self, "No Device", "Please select at least one device as the pool.")
                return

            device_pool = []
            for idx in dev_rows:
                item = self.seed_device_table.item(idx.row(), 0)
                if item:
                    parts = item.text().split('. ', 1)
                    if len(parts) == 2:
                        device_pool.append(parts[1].strip())

            # Build account list with their backup data
            account_queue = []
            backup_path = os.path.join(_PROJECT_ROOT, "account_backup")
            for idx in acc_rows:
                uid_item = self.seeding_account_table.item(idx.row(), 1)
                name_item = self.seeding_account_table.item(idx.row(), 2)
                if not uid_item:
                    continue
                uid = uid_item.text().strip()
                name = name_item.text() if name_item else uid
                # Find backup folder
                acc_folder = None
                if os.path.exists(backup_path):
                    for entry in os.scandir(backup_path):
                        if entry.is_dir() and entry.name.startswith(uid):
                            acc_folder = entry.path
                            break
                if not acc_folder:
                    self.add_activity(f"⚠ No backup found for {uid} — skipping")
                    continue
                # Load account_info.json
                jp = os.path.join(acc_folder, "account_info.json")
                acc_data = {}
                if os.path.exists(jp):
                    try:
                        with open(jp, 'r', encoding='utf-8') as f:
                            acc_data = json.load(f)
                    except Exception:
                        pass
                acc_data['account_uid'] = uid
                acc_data['_name'] = name
                account_queue.append(acc_data)

            if not account_queue:
                QMessageBox.warning(self, "No Accounts", "No valid accounts with backups found.")
                return

            device_ids = device_pool  # for logging
        else:
            # ── Normal mode: device-centric (original behavior) ───────────
            rows = self.seed_device_table.selectionModel().selectedRows()
            if not rows:
                QMessageBox.warning(self, "No Device", "Please select at least one device.")
                return
            device_ids = []
            for idx in rows:
                item = self.seed_device_table.item(idx.row(), 0)
                if item:
                    parts = item.text().split('. ', 1)
                    if len(parts) == 2:
                        device_ids.append(parts[1].strip())
            account_queue = []  # not used in normal mode

        reactions = []
        if mode == "react":
            react_map = [
                (getattr(self, 'seed_react_like_cb',  None), 'LIKE'),
                (getattr(self, 'seed_react_love_cb',  None), 'LOVE'),
                (getattr(self, 'seed_react_care_cb',  None), 'CARE'),
                (getattr(self, 'seed_react_haha_cb',  None), 'HAHA'),
                (getattr(self, 'seed_react_wow_cb',   None), 'WOW'),
                (getattr(self, 'seed_react_sad_cb',   None), 'SAD'),
                (getattr(self, 'seed_react_angry_cb', None), 'ANGRY'),
            ]
            reactions = [r for cb, r in react_map if cb and cb.isChecked()]
            if not reactions:
                QMessageBox.warning(self, "No Reaction", "Please select at least one reaction type.")
                return

        react_comments = []
        if mode == "react" and hasattr(self, '_seed_react_comment_layout'):
            for i in range(self._seed_react_comment_layout.count() - 1):
                item = self._seed_react_comment_layout.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), QCheckBox):
                    cb = item.widget()
                    if cb.isChecked(): react_comments.append(cb.text())

        comment_entries = []
        if mode == "comment" and hasattr(self, '_seed_comment_layout'):
            for i in range(self._seed_comment_layout.count() - 1):
                item = self._seed_comment_layout.itemAt(i)
                w = item.widget() if item else None
                if w:
                    cb = w.findChild(QCheckBox)
                    if cb and cb.isChecked():
                        t = w.property("entry_type"); v = w.property("entry_value")
                        if t and v: comment_entries.append((t, v))

        d_min = self.seed_delay_min.value() if hasattr(self, 'seed_delay_min') else 3
        d_max = self.seed_delay_max.value() if hasattr(self, 'seed_delay_max') else 8
        repeat = self.seed_repeat_spin.value() if hasattr(self, 'seed_repeat_spin') else 1
        open_app  = getattr(self, 'seed_open_app_cb',  None) and self.seed_open_app_cb.isChecked()
        close_app = getattr(self, 'seed_close_app_cb', None) and self.seed_close_app_cb.isChecked()
        skip_err  = getattr(self, 'seed_skip_error_cb', None) and self.seed_skip_error_cb.isChecked()

        self.seed_start_btn.setEnabled(False); self.seed_stop_btn.setEnabled(True)
        self._seeding_active = True
        if auto_restore:
            self.add_activity(f"▶ Seeding ({mode}) — Account-centric mode")
            self.add_activity(f"  {len(account_queue)} accounts → {len(device_ids)} device(s) pool")
        else:
            self.add_activity(f"▶ Seeding ({mode}) started — {len(device_ids)} device(s) selected: {', '.join(d[-8:] for d in device_ids)}")
        self.add_activity(f"  {type_label}: {url[:80]}")

        _adb_path = self.adb_path
        # Verify path exists, find correct one if not
        if not os.path.exists(_adb_path):
            base = _PROJECT_ROOT
            for candidate in [
                os.path.join(base, "platform-tools", "platform-tools", "adb.exe"),
                os.path.join(base, "platform-tools", "adb.exe"),
                "adb"
            ]:
                if candidate == "adb" or os.path.exists(candidate):
                    _adb_path = candidate
                    break

        class _FakeResult:
            stdout = ""; stderr = ""; returncode = 1

        def _adb(did, args, timeout=10):
            try:
                return safe_subprocess_run([_adb_path, "-s", did] + args,
                    capture_output=True, text=True, timeout=timeout)
            except Exception:
                return _FakeResult()

        def _shell(did, cmd, timeout=10):
            return _adb(did, ["shell"] + cmd, timeout)

        # ── XML cache — avoids redundant uiautomator dumps ────────────────────
        # Each device gets its own cache entry: (xml_str, timestamp)
        _xml_cache: dict = {}
        _XML_TTL = 1.5  # seconds before a cached dump is considered stale

        def _dump_ui(did, timeout=15, force=False):
            """Get UI XML. Uses a short-lived cache so multiple helpers in the same
            action don't each pay the full dump cost.
            Pass force=True to bypass the cache (e.g. after a tap).

            Strategy: try 'uiautomator dump' but cap it at 8s.
            If the device is busy (dump hangs), fall back to a fast
            'dumpsys window windows' check just to confirm FB is in foreground.
            """
            import time as _t
            now = _t.time()
            if not force:
                cached = _xml_cache.get(did)
                if cached and (now - cached[1]) < _XML_TTL:
                    return cached[0]
            try:
                # Use a short timeout — uiautomator can hang on busy devices
                _shell(did, ["uiautomator", "dump", "/sdcard/ui.xml"], timeout=min(timeout, 8))
            except Exception:
                return ""
            try:
                r = _shell(did, ["cat", "/sdcard/ui.xml"], timeout=5)
                xml = r.stdout or ""
                _xml_cache[did] = (xml, _t.time())
                return xml
            except Exception:
                return ""

        def _is_fb_foreground(did):
            """Fast check (< 0.5s) — returns True if Facebook Katana is the foreground app."""
            r = _shell(did, ["dumpsys", "window", "windows"], timeout=3)
            out = r.stdout or ""
            return "com.facebook.katana" in out

        def _wait_for_fb_foreground(did, max_wait=8):
            """Wait until FB is in foreground — much faster than waiting for full UI dump."""
            deadline = time.time() + max_wait
            while time.time() < deadline:
                if _is_fb_foreground(did):
                    return True
                time.sleep(0.3)
            return False

        def _invalidate_cache(did):
            """Call after any tap/swipe so next dump is fresh."""
            _xml_cache.pop(did, None)

        def _find_bounds_in_xml(xml, resource_id=None, text=None, desc=None):
            """Parse bounds from cached XML without triggering a new dump."""
            import re
            bounds_pat = r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            m = None
            if resource_id:
                rid_pat = f'resource-id="{re.escape(resource_id)}"'
                m = (re.search(f'{rid_pat}[^>]*{bounds_pat}', xml) or
                     re.search(f'{bounds_pat}[^>]*{rid_pat}', xml))
            elif text:
                txt_pat = f'text="{re.escape(text)}"'
                m = (re.search(f'{txt_pat}[^>]*{bounds_pat}', xml) or
                     re.search(f'{bounds_pat}[^>]*{txt_pat}', xml))
            elif desc:
                dsc_pat = f'content-desc="[^"]*{re.escape(desc)}[^"]*"'
                m = (re.search(f'{dsc_pat}[^>]*{bounds_pat}', xml) or
                     re.search(f'{bounds_pat}[^>]*{dsc_pat}', xml))
            if m:
                digits = [g for g in m.groups() if g.isdigit()]
                if len(digits) >= 4:
                    return int(digits[0]), int(digits[1]), int(digits[2]), int(digits[3])
            return None

        def _tap_element(did, resource_id=None, text=None, desc=None, timeout=8, xml=None):
            """Find and tap a UI element. Reuses xml if provided, otherwise dumps fresh."""
            if xml is None:
                xml = _dump_ui(did)
            coords = _find_bounds_in_xml(xml, resource_id=resource_id, text=text, desc=desc)
            if coords:
                x1, y1, x2, y2 = coords
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                _shell(did, ["input", "tap", str(cx), str(cy)])
                _invalidate_cache(did)
                return True
            return False

        def _open_url(did, url):
            """Open any Facebook URL directly in the Facebook app — no chooser dialog."""
            import re as _re2

            _shell(did, ["am", "start",
                "-a", "android.intent.action.VIEW",
                "-d", url,
                "--activity-single-top",
                "-n", "com.facebook.katana/com.facebook.katana.IntentUriHandler"],
                timeout=10)
            _invalidate_cache(did)

            # Step 1: fast foreground check (dumpsys, ~0.3s each) — wait up to 5s
            _wait_for_fb_foreground(did, max_wait=5)

            # Step 2: one UI dump to check for chooser dialog
            xml2 = _dump_ui(did, timeout=6, force=True)
            if "Just once" in xml2 or "Set to always" in xml2 or "Always" in xml2:
                if not (_tap_element(did, text="Set to always open", xml=xml2) or
                        _tap_element(did, text="Always", xml=xml2) or
                        _tap_element(did, text="ALWAYS", xml=xml2)):
                    _tap_element(did, text="Just once", xml=xml2) or _tap_element(did, text="JUST ONCE", xml=xml2)
                time.sleep(0.5)

            # Extra settle time for share-link redirects (in-app navigation after open)
            is_share = bool(_re2.search(r'/share(/[pv])?/', url))
            if is_share:
                time.sleep(2)

        def _long_press_element(did, resource_id=None, desc=None, duration=800, xml=None):
            """Long press a UI element. Reuses xml if provided."""
            if xml is None:
                xml = _dump_ui(did)
            coords = _find_bounds_in_xml(xml, resource_id=resource_id, desc=desc)
            if coords:
                x1, y1, x2, y2 = coords
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                _shell(did, ["input", "swipe", str(cx), str(cy), str(cx), str(cy), str(duration)])
                _invalidate_cache(did)
                return True
            return False

        def _type_text(did, text, restore_ime=True):
            """Type text — uses ADB keyboard for Unicode support.
            Set restore_ime=False to keep ADB keyboard active after typing
            (useful when you need to tap a send button before restoring).
            Returns the original IME so caller can restore it later if needed.
            """
            import urllib.parse
            cur_ime = _shell(did, ["settings", "get", "secure", "default_input_method"], timeout=5).stdout.strip()
            # Try ADB keyboard first
            _shell(did, ["ime", "enable", "com.android.adbkeyboard/.AdbIME"], timeout=3)
            _shell(did, ["ime", "set", "com.android.adbkeyboard/.AdbIME"], timeout=3)
            time.sleep(0.3)
            encoded = urllib.parse.quote(text)
            r = _shell(did, ["am", "broadcast", "-a", "ADB_INPUT_TEXT", "--es", "msg", encoded], timeout=5)
            adb_kb_worked = "result=-1" in (r.stdout or "") or "Broadcast completed" in (r.stdout or "")
            if not adb_kb_worked:
                # ADB keyboard not installed — use clipboard paste
                _shell(did, ["am", "broadcast", "-a", "clipper.set", "--es", "text", text], timeout=5)
                time.sleep(0.5)
                _shell(did, ["input", "keyevent", "KEYCODE_PASTE"], timeout=3)
                time.sleep(0.5)
                if not any(ord(c) > 127 for c in text):
                    _shell(did, ["input", "text", text.replace(' ', '%s').replace("'", "\\'")], timeout=10)
            time.sleep(0.3)
            if restore_ime and cur_ime and cur_ime not in ("null", ""):
                _shell(did, ["ime", "set", cur_ime], timeout=3)
            return cur_ime  # return so caller can restore later

        use_parallel = len(device_ids) > 1  # always parallel when multiple devices selected

        def _keep_screen_on(did):
            """
            Aggressively keep screen on for the duration of seeding.
            Uses multiple methods:
            1. Set screen timeout to max
            2. Enable stay-awake-while-plugged-in (developer option)
            3. Disable keyguard via settings
            4. Start a background heartbeat thread that wakes screen every 20s
            Returns (orig_timeout, orig_stay_on, heartbeat_thread_stop_event)
            """
            import threading as _thr

            # Save originals
            r1 = _shell(did, ["settings", "get", "system", "screen_off_timeout"], timeout=5)
            orig_timeout = (r1.stdout or "").strip() or "30000"

            r2 = _shell(did, ["settings", "get", "global", "stay_on_while_plugged_in"], timeout=5)
            orig_stay_on = (r2.stdout or "").strip() or "0"

            # Set screen timeout to maximum (30 min)
            _shell(did, ["settings", "put", "system", "screen_off_timeout", "1800000"], timeout=5)
            # Stay awake while plugged in (USB = 2, AC = 1, wireless = 4 — use 7 for all)
            _shell(did, ["settings", "put", "global", "stay_on_while_plugged_in", "7"], timeout=5)
            # Disable keyguard via secure settings
            _shell(did, ["settings", "put", "secure", "lockscreen.disabled", "1"], timeout=5)
            # Wake screen now
            _shell(did, ["input", "keyevent", "KEYCODE_WAKEUP"], timeout=5)
            _shell(did, ["wm", "dismiss-keyguard"], timeout=5)

            # Background heartbeat — wakes screen every 20 seconds
            stop_evt = _thr.Event()
            def _heartbeat():
                while not stop_evt.wait(20):
                    try:
                        _shell(did, ["input", "keyevent", "KEYCODE_WAKEUP"], timeout=3)
                        _shell(did, ["wm", "dismiss-keyguard"], timeout=3)
                    except Exception:
                        pass
            t = _thr.Thread(target=_heartbeat, daemon=True)
            t.start()

            return orig_timeout, orig_stay_on, stop_evt

        def _restore_screen_timeout(did, orig_data):
            """Stop heartbeat only — leave screen settings as-is so screen stays on after finish."""
            orig_timeout, orig_stay_on, stop_evt = orig_data
            stop_evt.set()  # stop heartbeat thread

        def _wait_for_post_loaded(did, max_wait=15):
            """Wait until the FB post reaction button is visible.
            Returns the XML string when found, or '' on timeout.

            Strategy:
            1. Fast-poll dumpsys (0.3s each) until FB is foreground — up to 8s
            2. One uiautomator dump to check if Like button is already visible
            3. If not, wait 3s and try once more — avoids hammering dump in a loop
            """
            import re as _re_w
            bounds_pat = r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            like_ids = [
                "com.facebook.katana:id/reaction_button",
                "com.facebook.katana:id/like_button",
                "com.facebook.katana:id/ufi_like_button",
            ]

            def _xml_has_like(xml):
                if not xml:
                    return False
                for rid in like_ids:
                    rid_pat = f'resource-id="{_re_w.escape(rid)}"'
                    if (_re_w.search(f'{rid_pat}[^>]*{bounds_pat}', xml) or
                            _re_w.search(f'{bounds_pat}[^>]*{rid_pat}', xml)):
                        return True
                return 'content-desc="Like"' in xml or 'content-desc="Reactions"' in xml

            # Phase 1: fast foreground check — wait until FB is active (cheap, ~0.3s each)
            _wait_for_fb_foreground(did, max_wait=8)

            # Phase 2: do at most (max_wait // 4) dump attempts with 3s gaps
            # Each dump takes ~4s, so 3 attempts = ~21s max instead of looping forever
            attempts = max(2, max_wait // 4)
            for _ in range(attempts):
                xml = _dump_ui(did, timeout=8, force=True)
                if _xml_has_like(xml):
                    return xml
                time.sleep(3)
            return ""

        def _run_device(did):
            adb = _adb_path; pkg = "com.facebook.katana"
            orig_data = _keep_screen_on(did)
            # Build shuffled cycles so all checked items are used evenly before repeating
            def _shuffled_cycle(items):
                pool = list(items)
                while True:
                    random.shuffle(pool)
                    yield from pool
            _react_gen        = _shuffled_cycle(reactions)     if reactions      else None
            _react_cmt_gen    = _shuffled_cycle(react_comments) if react_comments else None
            _comment_gen      = _shuffled_cycle(comment_entries) if comment_entries else None
            try:
                for _ in range(repeat):
                    if not self._seeding_active: break
                    try:
                        self.add_activity(f"  [{did[-8:]}] Opening post...")
                        _shell(did, ["input", "keyevent", "KEYCODE_WAKEUP"], timeout=3)
                        _shell(did, ["wm", "dismiss-keyguard"], timeout=3)

                        # Open Facebook first if needed
                        if open_app:
                            safe_subprocess_run([adb, "-s", did, "shell", "monkey", "-p", pkg,
                                "-c", "android.intent.category.LAUNCHER", "1"],
                                capture_output=True, text=True, timeout=15)
                            time.sleep(3)

                        # Navigate to post URL
                        _open_url(did, url)

                        # Fixed wait for post to load over network.
                        # Share links need extra time for in-app redirect.
                        import re as _re_load
                        _is_share_url = bool(_re_load.search(r'/share(/[pv])?/', url))
                        _load_wait = 6 if _is_share_url else 4
                        self.add_activity(f"  [{did[-8:]}] Waiting {_load_wait}s for post to load...")
                        time.sleep(_load_wait)

                        # One UI dump to get current state — reused by react/comment steps
                        post_xml = _dump_ui(did, force=True)
                        if not post_xml:
                            # Scroll down to reveal action bar and try once more
                            _shell(did, ["input", "swipe", "540", "900", "540", "600", "400"])
                            time.sleep(1)
                            post_xml = _dump_ui(did, force=True)

                        if mode == "react":
                            # ── STEP 2: React ──────────────────────────────
                            reaction = next(_react_gen)
                            self.add_activity(f"  [{did[-8:]}] Reacting with {reaction}...")
                            like_ids = ["com.facebook.katana:id/reaction_button",
                                        "com.facebook.katana:id/like_button",
                                        "com.facebook.katana:id/ufi_like_button"]
                            react_descs = {'LIKE':'Like','LOVE':'Love','CARE':'Care',
                                           'HAHA':'Haha','WOW':'Wow','SAD':'Sad','ANGRY':'Angry'}
                            react_label = react_descs.get(reaction, reaction)

                            # Try to long-press Like button using already-fetched post_xml
                            # First scroll down slightly to ensure the action bar (Like/Comment/Share) is visible
                            _shell(did, ["input", "swipe", "540", "800", "540", "500", "300"])
                            time.sleep(0.5)
                            current_xml = _dump_ui(did, force=True)  # fresh dump after scroll
                            opened = False
                            for _try in range(3):
                                _shell(did, ["input", "keyevent", "KEYCODE_WAKEUP"], timeout=3)
                                for rid in like_ids:
                                    coords = _find_bounds_in_xml(current_xml, resource_id=rid)
                                    if coords:
                                        x1, y1, x2, y2 = coords
                                        cx, cy = (x1+x2)//2, (y1+y2)//2
                                        _shell(did, ["input", "swipe", str(cx), str(cy), str(cx), str(cy), "1200"])
                                        _invalidate_cache(did)
                                        opened = True; break
                                if not opened:
                                    coords = _find_bounds_in_xml(current_xml, desc="Like")
                                    if coords:
                                        x1, y1, x2, y2 = coords
                                        cx, cy = (x1+x2)//2, (y1+y2)//2
                                        _shell(did, ["input", "swipe", str(cx), str(cy), str(cx), str(cy), "1200"])
                                        _invalidate_cache(did)
                                        opened = True
                                if opened:
                                    break
                                # Still not found — scroll more and get fresh dump
                                _shell(did, ["input", "swipe", "540", "900", "540", "500", "400"])
                                time.sleep(1)
                                current_xml = _dump_ui(did, force=True)

                            if not opened:
                                self.add_activity(f"  [{did[-8:]}] ⚠ Like button not found")

                            # Wait for reaction picker to animate open (~1.5s after long-press ends)
                            # Then ONE dump to find the reaction label by content-desc
                            time.sleep(1.5)
                            picker_xml = _dump_ui(did, force=True)
                            if not _tap_element(did, desc=react_label, xml=picker_xml):
                                # Not visible yet — wait 1s more and try once more
                                time.sleep(1.0)
                                picker_xml = _dump_ui(did, force=True)
                                if not _tap_element(did, desc=react_label, xml=picker_xml):
                                    # Last resort: tap Like directly
                                    self.add_activity(f"  [{did[-8:]}] ⚠ Picker not found — tapping Like")
                                    _tap_element(did, desc="Like", xml=picker_xml)
                            time.sleep(0.5)
                            self.add_activity(f"  [{did[-8:]}] ✓ Reacted {reaction}")

                            # ── STEP 3: Comment (optional) ─────────────────
                            if react_comments:
                                comment_text = next(_react_cmt_gen)
                                self.add_activity(f"  [{did[-8:]}] Commenting...")

                                # Give the post view time to settle after reaction
                                time.sleep(1.5)

                                # ONE dump to find comment button
                                cmt_xml = _dump_ui(did, force=True)
                                comment_ids = [
                                    "com.facebook.katana:id/comment_text",
                                    "com.facebook.katana:id/comment_composer_text",
                                    "com.facebook.katana:id/comment_box",
                                    "com.facebook.katana:id/comment_button",
                                    "com.facebook.katana:id/ufi_comment_button",
                                ]
                                tapped = any(_tap_element(did, resource_id=rid, xml=cmt_xml) for rid in comment_ids)
                                if not tapped:
                                    for hint in ["Write a comment", "Comment", "Add a comment"]:
                                        if (_tap_element(did, text=hint, xml=cmt_xml) or
                                                _tap_element(did, desc=hint, xml=cmt_xml)):
                                            tapped = True; break

                                if not tapped:
                                    self.add_activity(f"  [{did[-8:]}] ⚠ Comment box not found — skipping")
                                else:
                                    time.sleep(1.5)  # wait for keyboard to fully open

                                    # Type text but DON'T restore keyboard yet —
                                    # restoring keyboard causes comment box to lose focus
                                    # and the send button to disappear before we can tap it
                                    orig_ime = _type_text(did, comment_text, restore_ime=False)
                                    time.sleep(1.0)  # wait for text to appear in field

                                    # Dump UI to find the actual send button
                                    send_xml = _dump_ui(did, force=True)

                                    # Send button has content-desc="Send" with no resource-id
                                    # Try content-desc first, then resource-id fallbacks
                                    send_ids = [
                                        "com.facebook.katana:id/comment_post_button",
                                        "com.facebook.katana:id/send_button",
                                        "com.facebook.katana:id/submit_button",
                                        "com.facebook.katana:id/post_button",
                                        "com.facebook.katana:id/comment_send_button",
                                        "com.facebook.katana:id/composer_publish_button",
                                        "com.facebook.katana:id/primary_button",
                                        "com.facebook.katana:id/action_button",
                                    ]
                                    # content-desc="Send" is the actual button on this FB version
                                    sent = any(_tap_element(did, desc=d, xml=send_xml)
                                               for d in ["Send", "Post", "Submit", "Reply", "Comment"])
                                    if not sent:
                                        sent = any(_tap_element(did, resource_id=rid, xml=send_xml) for rid in send_ids)
                                    if not sent:
                                        # Last resort: Enter key
                                        _shell(did, ["input", "keyevent", "66"])
                                        self.add_activity(f"  [{did[-8:]}] ⚠ Send button not found — used Enter key")

                                    # NOW restore the original keyboard
                                    if orig_ime and orig_ime not in ("null", ""):
                                        _shell(did, ["ime", "set", orig_ime], timeout=3)

                                    # Wait for comment to post and verify
                                    time.sleep(2.5)
                                    verify_xml = _dump_ui(did, force=True)
                                    comment_sent = comment_text[:20] not in (verify_xml or "")
                                    if comment_sent:
                                        self.add_activity(f"  [{did[-8:]}] ✓ Commented")
                                    else:
                                        # Text still in box — retry send
                                        sent2 = any(_tap_element(did, resource_id=rid, xml=verify_xml) for rid in send_ids)
                                        if not sent2:
                                            _shell(did, ["input", "keyevent", "66"])
                                        time.sleep(2.0)
                                        self.add_activity(f"  [{did[-8:]}] ✓ Commented")

                            # ── STEP 4: Share (optional) ───────────────────
                            if getattr(self, 'seed_share_cb', None) and self.seed_share_cb.isChecked():
                                self.add_activity(f"  [{did[-8:]}] Sharing post...")
                                import re as _re_s
                                # Scroll back to top to reveal action bar
                                _shell(did, ["input", "keyevent", "111"])  # dismiss keyboard
                                time.sleep(0.5)
                                _shell(did, ["input", "swipe", "540", "900", "540", "300", "600"])
                                time.sleep(1)
                                share_xml = _dump_ui(did, force=True)
                                share_ids = [
                                    "com.facebook.katana:id/share_button",
                                    "com.facebook.katana:id/ufi_share_button",
                                    "com.facebook.katana:id/share_icon",
                                    "com.facebook.katana:id/action_share",
                                ]
                                shared = any(_tap_element(did, resource_id=rid, xml=share_xml) for rid in share_ids)
                                if not shared:
                                    shared = any(_tap_element(did, desc=d, xml=share_xml) for d in
                                                 ["Share", "Share post", "Share Post"])
                                if shared:
                                    time.sleep(2)
                                    confirm_xml = _dump_ui(did, force=True)
                                    confirmed = False
                                    for confirm in ["Share now", "Share to Feed", "Share to News Feed",
                                                    "Share Now", "SHARE NOW"]:
                                        if (_tap_element(did, desc=confirm, xml=confirm_xml) or
                                                _tap_element(did, text=confirm, xml=confirm_xml)):
                                            confirmed = True; break
                                    time.sleep(2)
                                    self.add_activity(f"  [{did[-8:]}] {'✓ Shared' if confirmed else '⚠ Share confirm not found'}")

                        elif mode == "comment" and comment_entries:
                            etype, evalue = next(_comment_gen)
                            self.add_activity(f"  [{did[-8:]}] Commenting ({etype})...")
                            comment_ids = [
                                "com.facebook.katana:id/comment_button",
                                "com.facebook.katana:id/ufi_comment_button",
                            ]
                            for rid in comment_ids:
                                if _tap_element(did, resource_id=rid): break
                            else:
                                _tap_element(did, desc="Comment")
                            time.sleep(2.5)
                            if etype == "text":
                                _type_text(did, evalue)
                                time.sleep(2)
                                sent = False
                                send_ids = [
                                    "com.facebook.katana:id/comment_post_button",
                                    "com.facebook.katana:id/send_button",
                                    "com.facebook.katana:id/submit_button",
                                ]
                                for _ in range(3):
                                    for rid in send_ids:
                                        if _tap_element(did, resource_id=rid):
                                            sent = True; break
                                    if sent: break
                                    if _tap_element(did, desc="Post") or _tap_element(did, desc="Send"):
                                        sent = True; break
                                    time.sleep(1)
                                if not sent:
                                    _shell(did, ["input", "keyevent", "66"])
                                time.sleep(2)
                            elif etype == "image":
                                remote = f"/sdcard/seed_{int(time.time())}.jpg"
                                safe_subprocess_run([adb, "-s", did, "push", evalue, remote],
                                    capture_output=True, timeout=30)
                                self.add_activity(f"  [{did[-8:]}] Image pushed, manual attach needed")
                            self.add_activity(f"  [{did[-8:]}] ✓ Comment done")

                        if close_app:
                            _shell(did, ["am", "force-stop", pkg])

                        time.sleep(random.uniform(d_min, d_max))

                    except Exception as e:
                        self.add_activity(f"  [{did[-8:]}] ✗ Error: {str(e)[:200]}")
                        if not skip_err:
                            pass  # continue iterating repeats
            finally:
                _restore_screen_timeout(did, orig_data)

        def _run():
            import concurrent.futures

            if auto_restore:
                # ── Account-centric mode ──────────────────────────────────
                # Distribute accounts round-robin across device pool.
                # Each device gets a queue and processes accounts sequentially.
                # All devices run in parallel.
                n_devices = len(device_ids)
                device_queues = {did: [] for did in device_ids}
                for i, acc_data in enumerate(account_queue):
                    device_queues[device_ids[i % n_devices]].append(acc_data)

                def _run_account_queue(did, queue):
                    """Process a queue of accounts on one device sequentially."""
                    for acc_data in queue:
                        if not self._seeding_active:
                            break
                        uid  = acc_data.get('account_uid', '')
                        name = acc_data.get('_name', uid)

                        # Update status in seeding table (thread-safe via signal)
                        def _set_status(u, txt, color="#FF9800"):
                            for r in range(self.seeding_account_table.rowCount()):
                                uid_item = self.seeding_account_table.item(r, 1)
                                if uid_item and uid_item.text() == u:
                                    s_item = self.seeding_account_table.item(r, 3)
                                    if s_item:
                                        s_item.setText(txt)
                                        s_item.setForeground(QColor(color))
                                    break

                        self._seed_status_signal.emit(uid, "Restoring...", "#FF9800")

                        self.add_activity(f"  [{did[-8:]}] 🔄 Restoring session: {name} ({uid[-8:]})")

                        # Restore session using fast restore
                        try:
                            # Use fast restore for 10x speed improvement
                            from src.utils.fast_restore import FastRestore
                            fast_restore = FastRestore(self.adb_path, log_fn=lambda m: self.add_activity(f"  {m}"))
                            
                            # Find backup folder
                            backup_path = os.path.join(_PROJECT_ROOT, "account_backup")
                            acc_folder = None
                            for entry in os.scandir(backup_path):
                                if entry.is_dir() and entry.name.startswith(uid):
                                    acc_folder = entry.path
                                    break
                            
                            if not acc_folder:
                                ok, msg, duration = False, "Backup folder not found", 0
                            else:
                                ok, msg, duration = fast_restore.restore_account_fast(acc_data, did, acc_folder)
                                
                        except Exception as e:
                            ok, msg, duration = False, str(e), 0

                        if not ok:
                            self.add_activity(f"  [{did[-8:]}] ✗ Restore failed: {msg[:100]}")
                            self._seed_status_signal.emit(uid, "✗ Failed", "#f44336")
                            if skip_err:
                                continue
                            else:
                                break

                        self.add_activity(f"  [{did[-8:]}] ✓ Session restored in {duration:.1f}s — seeding...")
                        self._seed_status_signal.emit(uid, "Seeding...", "#2196F3")

                        # Minimal wait for Facebook to initialize (fast restore already launches it)
                        time.sleep(2)

                        # Run the seeding action on this device
                        _run_device(did)

                        # Update status to Done
                        self._seed_status_signal.emit(uid, "✓ Done", "#4CAF50")

                        # Delay between accounts
                        if self._seeding_active:
                            time.sleep(random.uniform(d_min, d_max))

                # Run all device queues in parallel
                with concurrent.futures.ThreadPoolExecutor(max_workers=n_devices) as ex:
                    futures = {
                        ex.submit(_run_account_queue, did, queue): did
                        for did, queue in device_queues.items()
                        if queue
                    }
                    for f in concurrent.futures.as_completed(futures):
                        try:
                            f.result()
                        except Exception as e:
                            did = futures[f]
                            self.add_activity(f"  [{did[-8:]}] ✗ Thread error: {str(e)[:200]}")

            else:
                # ── Normal device-centric mode ────────────────────────────
                if use_parallel and len(device_ids) > 1:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=len(device_ids)) as ex:
                        futures = {ex.submit(_run_device, did): did for did in device_ids}
                        for f in concurrent.futures.as_completed(futures):
                            try:
                                f.result()
                            except Exception as e:
                                did = futures[f]
                                self.add_activity(f"  [{did[-8:]}] ✗ Thread error: {str(e)[:200]}")
                else:
                    for did in device_ids:
                        if not self._seeding_active: break
                        _run_device(did)

            QMetaObject.invokeMethod(self, "_on_seeding_done", Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=_run, daemon=True).start()

    @pyqtSlot(str, str, str)
    def _seed_set_status_slot(self, uid: str, text: str, color: str):
        """Thread-safe slot to update account status in the seeding table."""
        for r in range(self.seeding_account_table.rowCount()):
            uid_item = self.seeding_account_table.item(r, 1)
            if uid_item and uid_item.text() == uid:
                s_item = self.seeding_account_table.item(r, 3)
                if s_item:
                    s_item.setText(text)
                    s_item.setForeground(QColor(color))
                break

    @pyqtSlot()
    def _on_seeding_done(self):
        self._seeding_active = False
        self.seed_start_btn.setEnabled(True); self.seed_stop_btn.setEnabled(False)
        self.add_activity("✅ Seeding completed")
        msg = QMessageBox(self)
        msg.setWindowTitle("Seeding Complete")
        msg.setText("✅ Seeding completed successfully!")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStyleSheet("""
            QMessageBox { background-color: #1e1e1e; color: #ffffff; }
            QMessageBox QLabel { color: #ffffff; font-size: 13px; }
            QPushButton { background-color: #4CAF50; color: #ffffff; border-radius: 6px;
                          padding: 6px 20px; font-size: 12px; }
            QPushButton:hover { background-color: #45a049; }
        """)
        msg.exec()


    def _stop_seeding(self):
        """Stop seeding operation"""
        self._seeding_active = False
        self.seed_start_btn.setEnabled(True); self.seed_stop_btn.setEnabled(False)
        self.add_activity("⏹ Seeding stopped by user")

