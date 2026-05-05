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
            QTableWidget::item:selected { background-color: rgba(76,175,80,0.15); color: #4CAF50; }
            QHeaderView::section { background-color: #252525; color: #666666; padding: 6px 10px;
                border: none; border-bottom: 1px solid #3d3d3d; font-weight: 600; font-size: 10px; text-transform: uppercase; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: #3d3d3d; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #4CAF50; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """
        _BTN_GREEN = """QPushButton { background-color: #4CAF50; color: #ffffff; border: none;
            border-radius: 5px; padding: 7px 14px; font-size: 12px; font-weight: 600; }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #388E3C; }
            QPushButton:disabled { background-color: #2a2a2a; color: #555555; }"""
        _BTN_GHOST = """QPushButton { background-color: transparent; color: #888888; border: 1px solid #3d3d3d;
            border-radius: 5px; padding: 6px 12px; font-size: 11px; }
            QPushButton:hover { background-color: #2a2a2a; color: #cccccc; border-color: #555555; }"""
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


        # ══════════════════════════════════════════════════════════════
        # LEFT PANEL — Accounts (25%)
        # ══════════════════════════════════════════════════════════════
        left_panel = QFrame()
        left_panel.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-right: 1px solid #2a2a2a; }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(0)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        left_toolbar = QFrame(); left_toolbar.setFixedHeight(52); left_toolbar.setStyleSheet(_TOOLBAR_STYLE)
        lt_layout = QHBoxLayout(left_toolbar); lt_layout.setContentsMargins(14, 0, 10, 0); lt_layout.setSpacing(8)
        lt_title = QLabel("Accounts"); lt_title.setStyleSheet(_TITLE_STYLE)
        self.auto_seed_account_badge = QLabel("0 accounts"); self.auto_seed_account_badge.setStyleSheet(_BADGE_STYLE)
        lt_layout.addWidget(lt_title); lt_layout.addWidget(self.auto_seed_account_badge); lt_layout.addStretch()
        load_acc_btn = QPushButton(); load_acc_btn.setIcon(qta.icon('fa5s.sync-alt', color='#888888'))
        load_acc_btn.setFixedSize(26, 26); load_acc_btn.setToolTip("Reload accounts")
        load_acc_btn.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { background: #2a2a2a; border-radius: 4px; }")
        load_acc_btn.clicked.connect(self._load_seeding_accounts)
        lt_layout.addWidget(load_acc_btn)
        left_layout.addWidget(left_toolbar)

        # Accounts table
        self.seeding_account_table = QTableWidget()
        self.seeding_account_table.setColumnCount(3)
        self.seeding_account_table.setHorizontalHeaderLabels(["#", "UID", "Status"])
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
        acc_hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        acc_hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        left_layout.addWidget(self.seeding_account_table, 1)

        # Bottom stats
        left_stats = QFrame(); left_stats.setFixedHeight(36)
        left_stats.setStyleSheet("QFrame { background: #1e1e1e; border: none; border-top: 1px solid #2a2a2a; }")
        ls_layout = QHBoxLayout(left_stats); ls_layout.setContentsMargins(14, 0, 14, 0); ls_layout.setSpacing(16)
        self._seed_stat_total = QLabel("Total: 0"); self._seed_stat_total.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
        self._seed_stat_done  = QLabel("Done: 0");  self._seed_stat_done.setStyleSheet("color: #4CAF50; font-size: 11px; background: transparent;")
        self._seed_stat_fail  = QLabel("Failed: 0"); self._seed_stat_fail.setStyleSheet("color: #f44336; font-size: 11px; background: transparent;")
        for w in [self._seed_stat_total, self._seed_stat_done, self._seed_stat_fail]: ls_layout.addWidget(w)
        ls_layout.addStretch()
        left_layout.addWidget(left_stats)

        main_layout.addWidget(left_panel, 22)


        # ══════════════════════════════════════════════════════════════
        # CENTER PANEL — Seeding (React / Comment) (48%)
        # ══════════════════════════════════════════════════════════════
        center_panel = QFrame()
        center_panel.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-right: 1px solid #2a2a2a; }")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setSpacing(0)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        center_toolbar = QFrame(); center_toolbar.setFixedHeight(52); center_toolbar.setStyleSheet(_TOOLBAR_STYLE)
        ct_layout = QHBoxLayout(center_toolbar); ct_layout.setContentsMargins(14, 0, 14, 0); ct_layout.setSpacing(10)
        ct_title = QLabel("Seeding"); ct_title.setStyleSheet(_TITLE_STYLE)
        ct_layout.addWidget(ct_title); ct_layout.addStretch()

        # Mode toggle buttons
        self._seed_react_btn = QPushButton("  React")
        self._seed_react_btn.setIcon(qta.icon('fa5s.thumbs-up', color='#4CAF50'))
        self._seed_react_btn.setCheckable(True); self._seed_react_btn.setChecked(True)
        self._seed_comment_btn = QPushButton("  Comment")
        self._seed_comment_btn.setIcon(qta.icon('fa5s.comment', color='#888888'))
        self._seed_comment_btn.setCheckable(True)
        _toggle_style_on  = "QPushButton { background: rgba(76,175,80,0.15); color: #4CAF50; border: 1px solid #4CAF50; border-radius: 5px; padding: 5px 12px; font-size: 12px; font-weight: 600; }"
        _toggle_style_off = "QPushButton { background: transparent; color: #666666; border: 1px solid #3d3d3d; border-radius: 5px; padding: 5px 12px; font-size: 12px; }" \
                            "QPushButton:hover { background: #2a2a2a; color: #cccccc; }"
        self._seed_react_btn.setStyleSheet(_toggle_style_on)
        self._seed_comment_btn.setStyleSheet(_toggle_style_off)

        def _switch_react():
            self._seed_react_btn.setChecked(True); self._seed_comment_btn.setChecked(False)
            self._seed_react_btn.setStyleSheet(_toggle_style_on); self._seed_comment_btn.setStyleSheet(_toggle_style_off)
            self._seed_react_btn.setIcon(qta.icon('fa5s.thumbs-up', color='#4CAF50'))
            self._seed_comment_btn.setIcon(qta.icon('fa5s.comment', color='#888888'))
            self.seeding_stack.setCurrentIndex(0)
        def _switch_comment():
            self._seed_comment_btn.setChecked(True); self._seed_react_btn.setChecked(False)
            self._seed_comment_btn.setStyleSheet(_toggle_style_on); self._seed_react_btn.setStyleSheet(_toggle_style_off)
            self._seed_comment_btn.setIcon(qta.icon('fa5s.comment', color='#4CAF50'))
            self._seed_react_btn.setIcon(qta.icon('fa5s.thumbs-up', color='#888888'))
            self.seeding_stack.setCurrentIndex(1)
        self._seed_react_btn.clicked.connect(_switch_react)
        self._seed_comment_btn.clicked.connect(_switch_comment)
        ct_layout.addWidget(self._seed_react_btn); ct_layout.addWidget(self._seed_comment_btn)
        center_layout.addWidget(center_toolbar)

        # Stacked widget for React / Comment pages
        from PyQt6.QtWidgets import QStackedWidget
        self.seeding_stack = QStackedWidget()
        self.seeding_stack.setStyleSheet("background: transparent;")

        # ── React Page ──────────────────────────────────────────────
        react_page = QWidget(); react_page.setStyleSheet("background: transparent;")
        rp_layout = QVBoxLayout(react_page); rp_layout.setSpacing(14); rp_layout.setContentsMargins(16, 16, 16, 16)

        # Post URL input
        rp_url_label = QLabel("Post URL / ID"); rp_url_label.setStyleSheet(_SECTION_LABEL)
        self.seed_post_url_input = QLineEdit(); self.seed_post_url_input.setPlaceholderText("https://www.facebook.com/...")
        self.seed_post_url_input.setStyleSheet(_INPUT_STYLE); self.seed_post_url_input.setFixedHeight(36)
        rp_layout.addWidget(rp_url_label); rp_layout.addWidget(self.seed_post_url_input)

        # Reaction type
        react_type_label = QLabel("Reaction Type"); react_type_label.setStyleSheet(_SECTION_LABEL)
        self.seed_react_type = QComboBox(); self.seed_react_type.setStyleSheet(_COMBO_STYLE)
        self.seed_react_type.setFixedHeight(36)
        for r_name, r_icon in [("👍 Like","fa5s.thumbs-up"),("❤️ Love","fa5s.heart"),("😂 Haha","fa5s.laugh"),
                                ("😮 Wow","fa5s.surprise"),("😢 Sad","fa5s.sad-tear"),("😡 Angry","fa5s.angry")]:
            self.seed_react_type.addItem(r_name)
        rp_layout.addWidget(react_type_label); rp_layout.addWidget(self.seed_react_type)

        # Options row
        react_opts_row = QHBoxLayout(); react_opts_row.setSpacing(20)
        self.seed_react_random_cb = QCheckBox("Random reaction"); self.seed_react_random_cb.setStyleSheet(_CHECK_STYLE)
        self.seed_react_scroll_cb = QCheckBox("Scroll feed first"); self.seed_react_scroll_cb.setStyleSheet(_CHECK_STYLE)
        react_opts_row.addWidget(self.seed_react_random_cb); react_opts_row.addWidget(self.seed_react_scroll_cb)
        react_opts_row.addStretch()
        rp_layout.addLayout(react_opts_row)

        # Activity log for react
        react_log_label = QLabel("Activity"); react_log_label.setStyleSheet(_SECTION_LABEL)
        self.seed_react_log = QTextEdit(); self.seed_react_log.setReadOnly(True)
        self.seed_react_log.setStyleSheet("QTextEdit { background: #141414; color: #888888; border: 1px solid #2a2a2a; border-radius: 5px; font-size: 11px; font-family: monospace; padding: 6px; }")
        rp_layout.addWidget(react_log_label); rp_layout.addWidget(self.seed_react_log, 1)
        self.seeding_stack.addWidget(react_page)

        # ── Comment Page ─────────────────────────────────────────────
        comment_page = QWidget(); comment_page.setStyleSheet("background: transparent;")
        cp_layout = QVBoxLayout(comment_page); cp_layout.setSpacing(14); cp_layout.setContentsMargins(16, 16, 16, 16)

        cp_url_label = QLabel("Post URL / ID"); cp_url_label.setStyleSheet(_SECTION_LABEL)
        self.seed_comment_url_input = QLineEdit(); self.seed_comment_url_input.setPlaceholderText("https://www.facebook.com/...")
        self.seed_comment_url_input.setStyleSheet(_INPUT_STYLE); self.seed_comment_url_input.setFixedHeight(36)
        cp_layout.addWidget(cp_url_label); cp_layout.addWidget(self.seed_comment_url_input)

        cp_text_label = QLabel("Comments (one per line)"); cp_text_label.setStyleSheet(_SECTION_LABEL)
        self.seed_comment_input = QTextEdit(); self.seed_comment_input.setPlaceholderText("Great post!\nLove this!\nAmazing content...")
        self.seed_comment_input.setStyleSheet(_INPUT_STYLE); self.seed_comment_input.setFixedHeight(110)
        cp_layout.addWidget(cp_text_label); cp_layout.addWidget(self.seed_comment_input)

        comment_opts_row = QHBoxLayout(); comment_opts_row.setSpacing(20)
        self.seed_comment_random_cb = QCheckBox("Random order"); self.seed_comment_random_cb.setStyleSheet(_CHECK_STYLE)
        self.seed_comment_react_after_cb = QCheckBox("React after comment"); self.seed_comment_react_after_cb.setStyleSheet(_CHECK_STYLE)
        comment_opts_row.addWidget(self.seed_comment_random_cb); comment_opts_row.addWidget(self.seed_comment_react_after_cb)
        comment_opts_row.addStretch()
        cp_layout.addLayout(comment_opts_row)

        comment_log_label = QLabel("Activity"); comment_log_label.setStyleSheet(_SECTION_LABEL)
        self.seed_comment_log = QTextEdit(); self.seed_comment_log.setReadOnly(True)
        self.seed_comment_log.setStyleSheet("QTextEdit { background: #141414; color: #888888; border: 1px solid #2a2a2a; border-radius: 5px; font-size: 11px; font-family: monospace; padding: 6px; }")
        cp_layout.addWidget(comment_log_label); cp_layout.addWidget(self.seed_comment_log, 1)
        self.seeding_stack.addWidget(comment_page)

        center_layout.addWidget(self.seeding_stack, 1)

        # Bottom action bar
        center_action_bar = QFrame(); center_action_bar.setFixedHeight(56)
        center_action_bar.setStyleSheet("QFrame { background: #1e1e1e; border: none; border-top: 1px solid #2a2a2a; }")
        ca_layout = QHBoxLayout(center_action_bar); ca_layout.setContentsMargins(16, 0, 16, 0); ca_layout.setSpacing(10)
        self.seed_start_btn = QPushButton("  Start Seeding"); self.seed_start_btn.setIcon(qta.icon('fa5s.play', color='#ffffff'))
        self.seed_start_btn.setFixedHeight(36); self.seed_start_btn.setStyleSheet(_BTN_GREEN)
        self.seed_stop_btn = QPushButton("  Stop"); self.seed_stop_btn.setIcon(qta.icon('fa5s.stop', color='#f44336'))
        self.seed_stop_btn.setFixedHeight(36); self.seed_stop_btn.setEnabled(False)
        self.seed_stop_btn.setStyleSheet("QPushButton { background: transparent; color: #f44336; border: 1px solid #f44336; border-radius: 5px; padding: 6px 14px; font-size: 12px; font-weight: 600; } QPushButton:hover { background: rgba(244,67,54,0.1); } QPushButton:disabled { color: #3d3d3d; border-color: #2a2a2a; }")
        self.seed_progress_label = QLabel("Idle"); self.seed_progress_label.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
        self.seed_start_btn.clicked.connect(self._start_seeding)
        self.seed_stop_btn.clicked.connect(self._stop_seeding)
        ca_layout.addWidget(self.seed_start_btn); ca_layout.addWidget(self.seed_stop_btn)
        ca_layout.addStretch(); ca_layout.addWidget(self.seed_progress_label)
        center_layout.addWidget(center_action_bar)

        main_layout.addWidget(center_panel, 48)


        # ══════════════════════════════════════════════════════════════
        # RIGHT PANEL — Devices + Settings (30%)
        # ══════════════════════════════════════════════════════════════
        right_panel = QFrame()
        right_panel.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; }")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(0)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        right_toolbar = QFrame(); right_toolbar.setFixedHeight(52); right_toolbar.setStyleSheet(_TOOLBAR_STYLE)
        rt_layout = QHBoxLayout(right_toolbar); rt_layout.setContentsMargins(14, 0, 10, 0); rt_layout.setSpacing(8)
        rt_title = QLabel("Devices"); rt_title.setStyleSheet(_TITLE_STYLE)
        self.seed_device_count_label = QLabel("0 device(s)")
        self.seed_device_count_label.setStyleSheet("QLabel { background: transparent; color: #4CAF50; font-size: 12px; font-weight: 500; padding: 0; border: none; }")
        rt_layout.addWidget(rt_title); rt_layout.addWidget(self.seed_device_count_label); rt_layout.addStretch()
        refresh_dev_btn = QPushButton(); refresh_dev_btn.setIcon(qta.icon('fa5s.sync-alt', color='#888888'))
        refresh_dev_btn.setFixedSize(26, 26); refresh_dev_btn.setToolTip("Refresh devices")
        refresh_dev_btn.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { background: #2a2a2a; border-radius: 4px; }")
        refresh_dev_btn.clicked.connect(self._load_seeding_devices)
        rt_layout.addWidget(refresh_dev_btn)
        right_layout.addWidget(right_toolbar)

        # Device table
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
        right_layout.addWidget(self.seed_device_table)

        # ── Settings Section ─────────────────────────────────────────
        settings_scroll = QScrollArea(); settings_scroll.setWidgetResizable(True)
        settings_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollBar:vertical { background: transparent; width: 6px; } QScrollBar::handle:vertical { background: #3d3d3d; border-radius: 3px; }")
        settings_inner = QWidget(); settings_inner.setStyleSheet("background: transparent;")
        settings_layout = QVBoxLayout(settings_inner); settings_layout.setSpacing(12); settings_layout.setContentsMargins(14, 14, 14, 14)

        # Section divider
        divider = QFrame(); divider.setFixedHeight(1); divider.setStyleSheet("background: #2a2a2a;")
        settings_layout.addWidget(divider)

        # Seeding Settings header
        seed_settings_title = QLabel("Seeding Settings"); seed_settings_title.setStyleSheet(_SECTION_LABEL)
        settings_layout.addWidget(seed_settings_title)

        # Delay settings
        delay_row = QHBoxLayout(); delay_row.setSpacing(8)
        delay_label = QLabel("Delay between actions (s)"); delay_label.setStyleSheet("color: #888888; font-size: 12px; background: transparent;")
        self.seed_delay_min = QSpinBox(); self.seed_delay_min.setRange(1, 300); self.seed_delay_min.setValue(3)
        self.seed_delay_min.setFixedWidth(60); self.seed_delay_min.setStyleSheet(_SPIN_STYLE)
        delay_sep = QLabel("–"); delay_sep.setStyleSheet("color: #555555; background: transparent;")
        self.seed_delay_max = QSpinBox(); self.seed_delay_max.setRange(1, 300); self.seed_delay_max.setValue(8)
        self.seed_delay_max.setFixedWidth(60); self.seed_delay_max.setStyleSheet(_SPIN_STYLE)
        delay_row.addWidget(delay_label, 1); delay_row.addWidget(self.seed_delay_min)
        delay_row.addWidget(delay_sep); delay_row.addWidget(self.seed_delay_max)
        settings_layout.addLayout(delay_row)

        # Repeat count
        repeat_row = QHBoxLayout(); repeat_row.setSpacing(8)
        repeat_label = QLabel("Repeat per account"); repeat_label.setStyleSheet("color: #888888; font-size: 12px; background: transparent;")
        self.seed_repeat_spin = QSpinBox(); self.seed_repeat_spin.setRange(1, 50); self.seed_repeat_spin.setValue(1)
        self.seed_repeat_spin.setFixedWidth(60); self.seed_repeat_spin.setStyleSheet(_SPIN_STYLE)
        repeat_row.addWidget(repeat_label, 1); repeat_row.addWidget(self.seed_repeat_spin)
        settings_layout.addLayout(repeat_row)

        # Checkboxes
        self.seed_open_app_cb = QCheckBox("Open Facebook before action"); self.seed_open_app_cb.setStyleSheet(_CHECK_STYLE); self.seed_open_app_cb.setChecked(True)
        self.seed_close_app_cb = QCheckBox("Close Facebook after action"); self.seed_close_app_cb.setStyleSheet(_CHECK_STYLE); self.seed_close_app_cb.setChecked(True)
        self.seed_skip_error_cb = QCheckBox("Skip device on error"); self.seed_skip_error_cb.setStyleSheet(_CHECK_STYLE); self.seed_skip_error_cb.setChecked(True)
        self.seed_use_proxy_cb = QCheckBox("Use device proxy"); self.seed_use_proxy_cb.setStyleSheet(_CHECK_STYLE); self.seed_use_proxy_cb.setChecked(True)
        for cb in [self.seed_open_app_cb, self.seed_close_app_cb, self.seed_skip_error_cb, self.seed_use_proxy_cb]:
            settings_layout.addWidget(cb)

        settings_layout.addStretch()
        settings_scroll.setWidget(settings_inner)
        right_layout.addWidget(settings_scroll, 1)

        main_layout.addWidget(right_panel, 30)

        # Initial data load
        self._load_seeding_accounts()
        self._load_seeding_devices()

        return tab

    def _load_seeding_accounts(self):
        """Load accounts into the seeding account table"""
        try:
            self.seeding_account_table.setRowCount(0)
            backup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "account_backup")
            if not os.path.exists(backup_path):
                return
            count = 0
            for folder in sorted(os.listdir(backup_path)):
                jp = os.path.join(backup_path, folder, "account_info.json")
                if not os.path.exists(jp): continue
                try:
                    with open(jp, 'r', encoding='utf-8') as f: d = json.load(f)
                    uid = d.get('account_uid', d.get('uid', folder.split('_')[0]))
                    count += 1
                    row = self.seeding_account_table.rowCount()
                    self.seeding_account_table.insertRow(row)
                    n_item = QTableWidgetItem(str(count)); n_item.setForeground(QColor("#555555")); n_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    u_item = QTableWidgetItem(uid); u_item.setForeground(QColor("#4CAF50"))
                    s_item = QTableWidgetItem("Ready"); s_item.setForeground(QColor("#555555"))
                    for col, item in enumerate([n_item, u_item, s_item]):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        self.seeding_account_table.setItem(row, col, item)
                    self.seeding_account_table.setRowHeight(row, 36)
                except: pass
            self.auto_seed_account_badge.setText(f"{count} accounts")
            self._seed_stat_total.setText(f"Total: {count}")
        except Exception as e:
            print(f"Error loading seeding accounts: {e}")

    def _load_seeding_devices(self):
        """Load connected devices into the seeding device table"""
        try:
            self.seed_device_table.setRowCount(0)
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
            result = safe_subprocess_run([self.adb_path, "devices"], capture_output=True, text=True, timeout=10)
            count = 0
            for line in result.stdout.strip().split('\n')[1:]:
                if '\t' in line:
                    device_id, status = line.split('\t')
                    if status.strip() == 'device':
                        count += 1; device_id = device_id.strip()
                        proxy = proxy_cache.get(device_id, '—')
                        spoof = spoof_cache.get(device_id, '—')
                        row = self.seed_device_table.rowCount()
                        self.seed_device_table.insertRow(row)
                        self.seed_device_table.setRowHeight(row, 36)
                        d_item = QTableWidgetItem(f"{count}. {device_id}"); d_item.setForeground(QColor("#4CAF50"))
                        p_item = QTableWidgetItem(proxy); p_item.setForeground(QColor("#FF9800") if proxy != '—' else QColor("#555555"))
                        s_item = QTableWidgetItem(spoof); s_item.setForeground(QColor("#FF9800") if spoof != '—' else QColor("#555555"))
                        for col, item in enumerate([d_item, p_item, s_item]):
                            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                            self.seed_device_table.setItem(row, col, item)
            self.seed_device_count_label.setText(f"{count} device(s)")
        except Exception as e:
            print(f"Error loading seeding devices: {e}")

    def _start_seeding(self):
        """Start seeding operation"""
        mode = "react" if self.seeding_stack.currentIndex() == 0 else "comment"
        url = self.seed_post_url_input.text().strip() if mode == "react" else self.seed_comment_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a Post URL or ID.")
            return
        rows = self.seed_device_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "No Device", "Please select at least one device.")
            return
        self.seed_start_btn.setEnabled(False); self.seed_stop_btn.setEnabled(True)
        self._seeding_active = True
        self.seed_progress_label.setText("Running...")
        self.seed_progress_label.setStyleSheet("color: #4CAF50; font-size: 11px; background: transparent;")
        log = self.seed_react_log if mode == "react" else self.seed_comment_log
        log.append(f"▶ Starting {mode} seeding on {len(rows)} device(s)...")
        self.add_activity(f"▶ Seeding ({mode}) started — {len(rows)} device(s), URL: {url[:60]}")

    def _stop_seeding(self):
        """Stop seeding operation"""
        self._seeding_active = False
        self.seed_start_btn.setEnabled(True); self.seed_stop_btn.setEnabled(False)
        self.seed_progress_label.setText("Stopped")
        self.seed_progress_label.setStyleSheet("color: #f44336; font-size: 11px; background: transparent;")
        self.add_activity("⏹ Seeding stopped by user")

