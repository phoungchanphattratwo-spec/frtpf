"""
AutoRegMixin — Auto Reg Mixin methods.

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
from src.automation.url_normalizer import normalize_facebook_url, URL_TYPE_LABELS as _URL_TYPE_LABELS
from src.core.config import CONFIG_FILE

# Project root — 3 levels up from src/ui/mixins/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.core.subprocess_utils import safe_subprocess_run
# Lazy import — registration pulls in appium/selenium (300-700ms cold-start)
# Import only when a registration session actually starts
# MaxChangeWorker lazy-imported in methods that use it (saves 75ms cold-start)

class AutoRegMixin:
    """Mixin — methods are injected into MainWindow via multiple inheritance."""

    def clear_accounts_table(self):
        """Clear all accounts from the table."""
        self.accounts_table.setRowCount(0)
        self.add_activity("Accounts table cleared")
    

    def add_account_to_table(self, email, password, first_name, last_name, birthday, gender, device, status, notes=""):
        """Add a new account to the accounts table with all details."""
        if not hasattr(self, 'accounts_table'):
            return
            
        from datetime import datetime
        
        row = self.accounts_table.rowCount()
        self.accounts_table.insertRow(row)
        
        # Email (show "Phone Signup" if empty)
        email_display = email if email else "Phone Signup"
        email_item = QTableWidgetItem(email_display)
        if not email:
            email_item.setForeground(QColor("#888888"))  # Gray color for phone signup
        self.accounts_table.setItem(row, 0, email_item)
        
        # Password (visible)
        password_item = QTableWidgetItem(password)
        self.accounts_table.setItem(row, 1, password_item)
        
        # Name (First + Last)
        name_item = QTableWidgetItem(f"{first_name} {last_name}")
        self.accounts_table.setItem(row, 2, name_item)
        
        # DOB
        dob_item = QTableWidgetItem(birthday)
        self.accounts_table.setItem(row, 3, dob_item)
        
        # Gender
        gender_item = QTableWidgetItem(gender)
        self.accounts_table.setItem(row, 4, gender_item)
        
        # Device (short ID)
        device_short = device[-8:] if len(device) > 8 else device
        device_item = QTableWidgetItem(device_short)
        device_item.setToolTip(device)  # Show full device ID on hover
        self.accounts_table.setItem(row, 5, device_item)
        
        # Status with enhanced color coding and styling
        status_item = QTableWidgetItem(status)
        
        # Set colors based on status type
        if "Success" in status or "Completed" in status or "✅" in status:
            status_item.setBackground(QColor("#4CAF50"))  # Green background
            status_item.setForeground(QColor("#ffffff"))  # White text
        elif "Failed" in status or "Error" in status or "❌" in status:
            status_item.setBackground(QColor("#f44336"))  # Red background
            status_item.setForeground(QColor("#ffffff"))  # White text
        elif "Running" in status or "Starting" in status or "🟢" in status:
            status_item.setBackground(QColor("#FF9800"))  # Orange background
            status_item.setForeground(QColor("#ffffff"))  # White text
        elif "Waiting" in status or "Pending" in status or "⏳" in status:
            status_item.setBackground(QColor("#2196F3"))  # Blue background
            status_item.setForeground(QColor("#ffffff"))  # White text
        elif "Stopped" in status or "Cancelled" in status or "⏹️" in status:
            status_item.setBackground(QColor("#9E9E9E"))  # Gray background
            status_item.setForeground(QColor("#ffffff"))  # White text
        elif "Loading" in status or "Connecting" in status or "🔄" in status:
            status_item.setBackground(QColor("#9C27B0"))  # Purple background
            status_item.setForeground(QColor("#ffffff"))  # White text
        elif "Ready" in status or "Idle" in status or "⚪" in status:
            status_item.setBackground(QColor("#607D8B"))  # Blue-gray background
            status_item.setForeground(QColor("#ffffff"))  # White text
        else:
            # Default/Unknown status
            status_item.setBackground(QColor("#795548"))  # Brown background for unknown
            status_item.setForeground(QColor("#ffffff"))  # White text
        
        # Enhanced text styling
        font = status_item.font()
        font.setBold(True)
        font.setPointSize(10)  # Slightly larger font
        status_item.setFont(font)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add some padding and border radius effect through tooltip
        status_item.setToolTip(f"Status: {status}")
        
        self.accounts_table.setItem(row, 6, status_item)
        
        # Created time
        time_item = QTableWidgetItem(datetime.now().strftime("%H:%M:%S"))
        self.accounts_table.setItem(row, 7, time_item)
        
        # Scroll to bottom
        self.accounts_table.scrollToBottom()
        self._update_ar_stats()


    def _update_ar_stats(self):
        if not hasattr(self, 'accounts_table') or not hasattr(self, 'ar_total_label'):
            return
        total = self.accounts_table.rowCount()
        done = failed = 0
        for r in range(total):
            item = self.accounts_table.item(r, 6)
            if item:
                s = item.text()
                if "Success" in s or "Completed" in s:
                    done += 1
                elif "Failed" in s or "Error" in s:
                    failed += 1
        self.ar_total_label.setText(f"Total: {total}")
        self.ar_done_label.setText(f"Done: {done}")
        self.ar_failed_label.setText(f"Failed: {failed}")
    

    def update_account_status(self, email, status, notes=""):
        """Update the status of an existing account in the table."""
        if not hasattr(self, 'accounts_table'):
            return
            
        # Find the row with this email
        for row in range(self.accounts_table.rowCount()):
            email_item = self.accounts_table.item(row, 0)
            if email_item and email_item.text() == email:
                # Update status (column 6) with enhanced color coding
                status_item = QTableWidgetItem(status)
                
                # Set colors based on status type
                if "Success" in status or "Completed" in status or "✅" in status:
                    status_item.setBackground(QColor("#4CAF50"))  # Green background
                    status_item.setForeground(QColor("#ffffff"))  # White text
                elif "Failed" in status or "Error" in status or "❌" in status:
                    status_item.setBackground(QColor("#f44336"))  # Red background
                    status_item.setForeground(QColor("#ffffff"))  # White text
                elif "Running" in status or "Starting" in status or "🟢" in status:
                    status_item.setBackground(QColor("#FF9800"))  # Orange background
                    status_item.setForeground(QColor("#ffffff"))  # White text
                elif "Waiting" in status or "Pending" in status or "⏳" in status:
                    status_item.setBackground(QColor("#2196F3"))  # Blue background
                    status_item.setForeground(QColor("#ffffff"))  # White text
                elif "Stopped" in status or "Cancelled" in status or "⏹️" in status:
                    status_item.setBackground(QColor("#9E9E9E"))  # Gray background
                    status_item.setForeground(QColor("#ffffff"))  # White text
                elif "Loading" in status or "Connecting" in status or "🔄" in status:
                    status_item.setBackground(QColor("#9C27B0"))  # Purple background
                    status_item.setForeground(QColor("#ffffff"))  # White text
                elif "Ready" in status or "Idle" in status or "⚪" in status:
                    status_item.setBackground(QColor("#607D8B"))  # Blue-gray background
                    status_item.setForeground(QColor("#ffffff"))  # White text
                else:
                    # Default/Unknown status
                    status_item.setBackground(QColor("#795548"))  # Brown background for unknown
                    status_item.setForeground(QColor("#ffffff"))  # White text
                
                # Enhanced text styling
                font = status_item.font()
                font.setBold(True)
                font.setPointSize(10)  # Slightly larger font
                status_item.setFont(font)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                # Add tooltip for status details
                status_item.setToolTip(f"Status: {status}")
                
                self.accounts_table.setItem(row, 6, status_item)
                self._update_ar_stats()
                break

    def renumber_account_rows(self):
        """Renumber the # column after row deletion"""
        if not hasattr(self, 'account_table'):
            return
        for row in range(self.account_table.rowCount()):
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setForeground(QColor("#888888"))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.account_table.setItem(row, 0, num_item)


    def edit_first_names(self):
        """Open dialog to edit first names list."""
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_edit_first"))
        dialog.setFixedSize(400, 300)
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
                font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', 'Courier New', monospace;
                font-size: 12px;
                padding: 8px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 0px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        
        # Instructions
        instructions = QLabel("Enter first names (one per line):")
        instructions.setStyleSheet("color: #00bcd4; font-weight: bold;")
        layout.addWidget(instructions)
        
        # Text area
        text_edit = QTextEdit()
        current_names = self.first_name_input.text().replace(", ", "\n")
        text_edit.setPlainText(current_names)
        layout.addWidget(text_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #666666;")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            names = [name.strip() for name in text_edit.toPlainText().split('\n') if name.strip()]
            self.first_name_input.setText(", ".join(names))
    

    def edit_last_names(self):
        """Open dialog to edit last names list."""
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_edit_last"))
        dialog.setFixedSize(400, 300)
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
                font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', 'Courier New', monospace;
                font-size: 12px;
                padding: 8px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 0px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        
        # Instructions
        instructions = QLabel("Enter last names (one per line):")
        instructions.setStyleSheet("color: #00bcd4; font-weight: bold;")
        layout.addWidget(instructions)
        
        # Text area
        text_edit = QTextEdit()
        current_names = self.last_name_input.text().replace(", ", "\n")
        text_edit.setPlainText(current_names)
        layout.addWidget(text_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #666666;")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            names = [name.strip() for name in text_edit.toPlainText().split('\n') if name.strip()]
            self.last_name_input.setText(", ".join(names))
    

    def toggle_signup_method(self):
        """Toggle between email and phone signup methods."""
        use_email = self.use_email_checkbox.isChecked()
        use_phone = self.use_phone_checkbox.isChecked()
        
        # Ensure at least one is selected
        if not use_email and not use_phone:
            # If user unchecks both, keep the one they didn't just uncheck
            sender = self.sender()
            if sender == self.use_email_checkbox:
                self.use_phone_checkbox.setChecked(True)
            else:
                self.use_email_checkbox.setChecked(True)
            return
        
        # If both are checked, uncheck the other one (exclusive selection)
        if use_email and use_phone:
            sender = self.sender()
            if sender == self.use_email_checkbox:
                self.use_phone_checkbox.setChecked(False)
            else:
                self.use_email_checkbox.setChecked(False)
        
        # Update field states
        email_enabled = self.use_email_checkbox.isChecked()
        phone_enabled = self.use_phone_checkbox.isChecked()
        
        # Update checkbox label colors
        if email_enabled:
            self.use_email_checkbox.setStyleSheet("""
                QCheckBox {
                    color: #4CAF50;
                    font-size: 12px;
                    font-weight: 600;
                    spacing: 6px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 0px;
                    border: 1px solid #3a3a3a;
                    background-color: #2a2a2a;
                }
                QCheckBox::indicator:checked {
                    background-color: #4CAF50;
                    border: 1px solid #4CAF50;
                }
            """)
        else:
            self.use_email_checkbox.setStyleSheet("""
                QCheckBox {
                    color: #555555;
                    font-size: 12px;
                    font-weight: 600;
                    spacing: 6px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 0px;
                    border: 1px solid #3a3a3a;
                    background-color: #2a2a2a;
                }
                QCheckBox::indicator:checked {
                    background-color: #4CAF50;
                    border: 1px solid #4CAF50;
                }
            """)
        
        if phone_enabled:
            self.use_phone_checkbox.setStyleSheet("""
                QCheckBox {
                    color: #FF9800;
                    font-size: 12px;
                    font-weight: 600;
                    spacing: 6px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 0px;
                    border: 1px solid #3a3a3a;
                    background-color: #2a2a2a;
                }
                QCheckBox::indicator:checked {
                    background-color: #FF9800;
                    border: 1px solid #FF9800;
                }
            """)
        else:
            self.use_phone_checkbox.setStyleSheet("""
                QCheckBox {
                    color: #555555;
                    font-size: 12px;
                    font-weight: 600;
                    spacing: 6px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 0px;
                    border: 1px solid #3a3a3a;
                    background-color: #2a2a2a;
                }
                QCheckBox::indicator:checked {
                    background-color: #FF9800;
                    border: 1px solid #FF9800;
                }
            """)
        
        # Enable/disable email fields
        self.email_display.setEnabled(email_enabled)
        self.email_input.setEnabled(email_enabled)
        
        # Email button is now in Advanced Settings dialog, not in main UI
        
        # Enable/disable phone fields
        self.phone_input.setEnabled(phone_enabled)
        self.country_code_input.setEnabled(phone_enabled and self.random_phone_checkbox.isChecked())
        
        # Email display is hidden (moved to Advanced Settings)
        # self.email_display.setVisible(email_enabled)
    

    def toggle_random_phone(self, state):
        """Toggle random phone number generation."""
        if state:  # Random phone enabled
            # Automatically enable "Use Phone Number" if not already checked
            if not self.use_phone_checkbox.isChecked():
                self.use_phone_checkbox.setChecked(True)
            
            # Enable country code dropdown
            self.country_code_input.setEnabled(True)
            # Disable manual phone input when random is enabled
            self.phone_input.setReadOnly(True)
            self.phone_input.setEnabled(False)
            self.phone_input.setPlaceholderText("Random phone numbers will be generated per account")
            self.phone_input.setStyleSheet("""
                QLineEdit {
                    background-color: #2a2a2a;
                    border: 1px solid #3a3a3a;
                    border-radius: 0px;
                    padding: 10px 12px;
                    color: #FF9800;
                    font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', 'Courier New', monospace;
                    font-size: 13px;
                }
            """)
        else:  # Random phone disabled
            # Disable country code dropdown
            self.country_code_input.setEnabled(False)
            # Enable manual input
            self.phone_input.setReadOnly(False)
            self.phone_input.setEnabled(self.use_phone_checkbox.isChecked())
            self.phone_input.setPlaceholderText("Enter phone number (optional for random)")
            self.phone_input.setStyleSheet("")  # Reset to default
    

    def generate_random_phone(self, country_code=None):
        """Generate a random phone number based on country code with VALID formats."""
        import random
        
        # If no country code provided, get from dropdown
        if not country_code:
            country_text = self.country_code_input.currentText()
            # Extract just the code (e.g., "+1" from "+1 (US/Canada)")
            country_code = country_text.split(' ')[0]
        
        # Remove + sign for processing
        code = country_code.replace('+', '')
        
        # Generate random digits based on VALID phone formats for each country
        if code == '1':  # US/Canada: +1 XXX-XXX-XXXX (10 digits)
            # Use VALID US/Canada area codes
            valid_area_codes = [
                # Major US area codes
                '201', '202', '203', '205', '206', '207', '208', '209', '210', '212', '213', '214', '215', '216', '217', '218', '219',
                '224', '225', '228', '229', '231', '234', '239', '240', '248', '251', '252', '253', '254', '256', '260', '262', '267',
                '269', '270', '272', '276', '281', '301', '302', '303', '304', '305', '307', '308', '309', '310', '312', '313', '314',
                '315', '316', '317', '318', '319', '320', '321', '323', '325', '330', '331', '334', '336', '337', '339', '346', '347',
                '351', '352', '360', '361', '364', '380', '385', '386', '401', '402', '404', '405', '406', '407', '408', '409', '410',
                '412', '413', '414', '415', '417', '419', '423', '424', '425', '430', '432', '434', '435', '440', '442', '443', '458',
                '463', '469', '470', '475', '478', '479', '480', '484', '501', '502', '503', '504', '505', '507', '508', '509', '510',
                '512', '513', '515', '516', '517', '518', '520', '530', '531', '534', '539', '540', '541', '551', '559', '561', '562',
                '563', '564', '567', '570', '571', '573', '574', '575', '580', '585', '586', '601', '602', '603', '605', '606', '607',
                '608', '609', '610', '612', '614', '615', '616', '617', '618', '619', '620', '623', '626', '628', '629', '630', '631',
                '636', '641', '646', '650', '651', '657', '660', '661', '662', '667', '669', '678', '680', '681', '682', '701', '702',
                '703', '704', '706', '707', '708', '712', '713', '714', '715', '716', '717', '718', '719', '720', '724', '725', '727',
                '731', '732', '734', '737', '740', '747', '754', '757', '760', '762', '763', '765', '769', '770', '772', '773', '774',
                '775', '779', '781', '785', '786', '801', '802', '803', '804', '805', '806', '808', '810', '812', '813', '814', '815',
                '816', '817', '818', '828', '830', '831', '832', '843', '845', '847', '848', '850', '856', '857', '858', '859', '860',
                '862', '863', '864', '865', '870', '872', '878', '901', '903', '904', '906', '907', '908', '909', '910', '912', '913',
                '914', '915', '916', '917', '918', '919', '920', '925', '928', '929', '930', '931', '936', '937', '940', '941', '947',
                '949', '951', '952', '954', '956', '959', '970', '971', '972', '973', '978', '979', '980', '984', '985', '989',
            ]
            area_code = random.choice(valid_area_codes)
            # Generate valid exchange (200-999, but not 555 for first 3 digits)
            exchange = random.randint(200, 999)
            while exchange == 555:  # Avoid 555 (reserved for fictional numbers)
                exchange = random.randint(200, 999)
            # Generate last 4 digits
            line_number = random.randint(0, 9999)
            number = f"+1{area_code}{exchange:03d}{line_number:04d}"
            
        elif code == '44':  # UK: +44 XXXX XXXXXX (10 digits)
            # Valid UK mobile prefixes: 7XXX
            prefix = random.randint(7000, 7999)
            suffix = random.randint(100000, 999999)
            number = f"+44{prefix}{suffix}"
            
        elif code == '855':  # Cambodia: +855 XX XXX XXXX (8-9 digits)
            # Valid Cambodia prefixes from all carriers
            valid_prefixes = [
                # Cellcard
                '011', '012', '017', '061', '076', '077', '078', '079', '085', '089', '092', '095', '099',
                # Smart
                '010', '015', '016', '069', '070', '081', '086', '087', '093', '096', '098',
                # Metfone
                '031', '060', '066', '067', '068', '071', '088', '090', '097'
            ]
            prefix = random.choice(valid_prefixes)
            # Generate 6 more random digits (total 8 digits after country code)
            suffix = random.randint(100000, 999999)
            number = f"+855{prefix}{suffix}"
            
        elif code == '84':  # Vietnam: +84 XX XXX XXXX (9 digits)
            # Valid Vietnam mobile prefixes: 3, 5, 7, 8, 9
            valid_prefixes = ['32', '33', '34', '35', '36', '37', '38', '39', '56', '58', '59', '70', '76', '77', '78', '79', '81', '82', '83', '84', '85', '86', '88', '89', '90', '91', '92', '93', '94', '96', '97', '98', '99']
            prefix = random.choice(valid_prefixes)
            suffix = random.randint(1000000, 9999999)
            number = f"+84{prefix}{suffix}"
            
        elif code == '86':  # China: +86 1XX XXXX XXXX (11 digits)
            # Valid China mobile prefixes: 13X, 14X, 15X, 16X, 17X, 18X, 19X
            first_digit = random.choice(['13', '14', '15', '16', '17', '18', '19'])
            second_digit = random.randint(0, 9)
            suffix = random.randint(10000000, 99999999)
            number = f"+86{first_digit}{second_digit}{suffix}"
            
        elif code == '91':  # India: +91 XXXXX XXXXX (10 digits)
            # Valid India mobile prefixes: 6, 7, 8, 9
            prefix = random.choice(['6', '7', '8', '9'])
            suffix = random.randint(000000000, 999999999)
            number = f"+91{prefix}{suffix:09d}"
            
        elif code == '62':  # Indonesia: +62 8XX XXXX XXXX (10-12 digits)
            # Valid Indonesia mobile prefixes: 81, 82, 83, 85, 87, 88, 89
            valid_prefixes = ['811', '812', '813', '814', '815', '816', '817', '818', '819', '821', '822', '823', '831', '832', '833', '838', '851', '852', '853', '855', '856', '857', '858', '859', '877', '878', '881', '882', '883', '884', '885', '886', '887', '888', '889', '895', '896', '897', '898', '899']
            prefix = random.choice(valid_prefixes)
            suffix = random.randint(1000000, 9999999)
            number = f"+62{prefix}{suffix}"
            
        elif code == '63':  # Philippines: +63 9XX XXX XXXX (10 digits)
            # Valid Philippines mobile prefixes: 9XX
            prefix = random.randint(900, 999)
            suffix = random.randint(1000000, 9999999)
            number = f"+63{prefix}{suffix}"
            
        elif code == '66':  # Thailand: +66 XX XXX XXXX (9 digits)
            # Valid Thailand mobile prefixes: 6, 8, 9
            valid_prefixes = ['61', '62', '63', '64', '65', '66', '80', '81', '82', '83', '84', '85', '86', '87', '88', '89', '90', '91', '92', '93', '94', '95', '96', '97', '98', '99']
            prefix = random.choice(valid_prefixes)
            suffix = random.randint(1000000, 9999999)
            number = f"+66{prefix}{suffix}"
            
        elif code == '60':  # Malaysia: +60 1X XXX XXXX (9-10 digits)
            # Valid Malaysia mobile prefixes: 10, 11, 12, 13, 14, 15, 16, 17, 18, 19
            prefix = random.randint(10, 19)
            suffix = random.randint(1000000, 9999999)
            number = f"+60{prefix}{suffix}"
            
        elif code == '81':  # Japan: +81 XX XXXX XXXX (10 digits)
            # Valid Japan mobile prefixes: 70, 80, 90
            valid_prefixes = ['70', '80', '90']
            prefix = random.choice(valid_prefixes)
            suffix = random.randint(10000000, 99999999)
            number = f"+81{prefix}{suffix}"
            
        elif code == '82':  # South Korea: +82 1X XXXX XXXX (10 digits)
            # Valid South Korea mobile prefixes: 10, 11
            prefix = random.choice(['10', '11'])
            suffix = random.randint(10000000, 99999999)
            number = f"+82{prefix}{suffix}"
            
        elif code == '65':  # Singapore: +65 XXXX XXXX (8 digits)
            # Valid Singapore mobile prefixes: 8, 9
            prefix = random.choice(['8', '9'])
            suffix = random.randint(0000000, 9999999)
            number = f"+65{prefix}{suffix:07d}"
            
        elif code == '61':  # Australia: +61 4XX XXX XXX (9 digits)
            # Valid Australia mobile prefix: 4
            prefix = random.randint(400, 499)
            suffix = random.randint(100000, 999999)
            number = f"+61{prefix}{suffix}"
            
        else:  # Generic format: country code + 8-10 random digits
            number = f"+{code}{random.randint(10000000, 9999999999)}"
        
        return number
    

    def generate_random_password(self):
        """Generate a random secure password."""
        import random
        import string
        
        # Password components
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        special = "!@#$%^&*"
        
        # Ensure at least one of each type
        password = [
            random.choice(uppercase),
            random.choice(lowercase),
            random.choice(digits),
            random.choice(special)
        ]
        
        # Fill the rest with random characters (total length 12-16)
        length = random.randint(12, 16)
        all_chars = uppercase + lowercase + digits + special
        password.extend(random.choice(all_chars) for _ in range(length - 4))
        
        # Shuffle to avoid predictable patterns
        random.shuffle(password)
        
        return ''.join(password)
    

    def toggle_random_password(self, state):
        """Toggle random password generation."""
        if state:  # Checkbox is checked
            self.password_input.setEnabled(False)
            self.password_input.setPlaceholderText("Random password per account")
            self.password_input.setText("")
            self.password_input.setStyleSheet("color: #888888;")
        else:  # Checkbox is unchecked
            self.password_input.setEnabled(True)
            self.password_input.setPlaceholderText("Same for all accounts")
            self.password_input.setText("SecurePass123!")
            self.password_input.setStyleSheet("")  # Reset to default
    

    def toggle_reg_novary(self, state):
        """Toggle Reg Novary - disables Verification when checked."""
        if state:  # Reg Novary is checked
            self.verification_checkbox.setEnabled(False)
            self.verification_checkbox.setChecked(False)
        else:  # Reg Novary is unchecked
            self.verification_checkbox.setEnabled(True)
    

    def toggle_verification(self, state):
        """Toggle Verification - disables Reg Novary when checked."""
        if state:  # Verification is checked
            self.reg_novary_checkbox.setEnabled(False)
            self.reg_novary_checkbox.setChecked(False)
            # Open verification methods dialog
            self.open_verification_dialog()
        else:  # Verification is unchecked
            self.reg_novary_checkbox.setEnabled(True)
    

    def toggle_auto_names(self, state):
        """Toggle between custom names and auto-generated English names."""
        if state:  # Checkbox is checked
            # Generate random English names
            self.generate_random_english_names()
            self.names_display.setStyleSheet("color: #00bcd4;")  # Highlight in cyan
            self.update_names_display()
        else:  # Checkbox is unchecked
            # Restore original custom names
            self.names_display.setStyleSheet("")  # Reset style
            self.update_names_display()
    

    def generate_random_english_names(self):
        """Generate random English first and last names."""
        import random
        
        # Common English first names
        male_first_names = [
            "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
            "Thomas", "Charles", "Christopher", "Daniel", "Matthew", "Anthony", "Mark",
            "Donald", "Steven", "Paul", "Andrew", "Joshua", "Kenneth", "Kevin", "Brian",
            "George", "Edward", "Ronald", "Timothy", "Jason", "Jeffrey", "Ryan", "Jacob",
            "Gary", "Nicholas", "Eric", "Jonathan", "Stephen", "Larry", "Justin", "Scott"
        ]
        
        female_first_names = [
            "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan",
            "Jessica", "Sarah", "Karen", "Nancy", "Lisa", "Betty", "Margaret", "Sandra",
            "Ashley", "Dorothy", "Kimberly", "Emily", "Donna", "Michelle", "Carol",
            "Amanda", "Melissa", "Deborah", "Stephanie", "Rebecca", "Laura", "Sharon",
            "Cynthia", "Kathleen", "Amy", "Shirley", "Angela", "Helen", "Anna", "Brenda"
        ]
        
        # Common English last names
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
            "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
            "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Thompson", "White",
            "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
            "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
            "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell"
        ]
        
        # Combine male and female names
        all_first_names = male_first_names + female_first_names
        
        # Randomly select 5-10 first names and 5-10 last names
        num_first = random.randint(5, 10)
        num_last = random.randint(5, 10)
        
        selected_first = random.sample(all_first_names, num_first)
        selected_last = random.sample(last_names, num_last)
        
        # Update the hidden fields
        self.first_name_input.setText(", ".join(selected_first))
        self.last_name_input.setText(", ".join(selected_last))
    

    def update_names_display(self):
        """Update the display field with current name combinations."""
        first_text = self.first_name_input.text().strip()
        last_text = self.last_name_input.text().strip()
        
        # Check if names are empty
        if not first_text or not last_text:
            self.names_display.setText("")
            return
        
        first_names = [n.strip() for n in first_text.split(",") if n.strip()]
        last_names = [n.strip() for n in last_text.split(",") if n.strip()]
        
        # Check if we have valid names
        if not first_names or not last_names:
            self.names_display.setText("")
            return
        
        # Show first 3 combinations as preview
        preview = []
        count = 0
        for first in first_names[:2]:
            for last in last_names[:2]:
                if count < 3:
                    preview.append(f"{first} {last}")
                    count += 1
        
        total = len(first_names) * len(last_names)
        display_text = ", ".join(preview)
        if total > 3:
            display_text += f"... ({total} total)"
        
        self.names_display.setText(display_text)
    

    def edit_custom_names(self):
        """Open dialog to edit both first and last names with modern design."""
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_edit_custom"))
        dialog.setMinimumSize(900, 560)
        dialog.setStyleSheet("""
            QDialog { background-color: #1e1e1e; }
            QLabel { color: #cccccc; font-size: 12px; background: transparent; }
            QTextEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                color: #cccccc;
                font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', 'Courier New', monospace;
                font-size: 13px;
                padding: 10px;
            }
            QTextEdit:focus { border: 1px solid #4CAF50; }
            QComboBox, QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 7px 10px;
                color: #cccccc;
                font-size: 12px;
            }
            QComboBox:hover, QLineEdit:hover { border-color: #4CAF50; }
            QComboBox:focus, QLineEdit:focus { border-color: #4CAF50; }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #888888;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                color: #cccccc;
                selection-background-color: rgba(76,175,80,0.2);
                outline: none;
            }
        """)

        main_layout = QVBoxLayout(dialog)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ── Header bar ────────────────────────────────────────────────────
        header_bar = QFrame()
        header_bar.setFixedHeight(48)
        header_bar.setStyleSheet("QFrame { background: transparent; border: none; border-bottom: 1px solid #3d3d3d; }")
        hb_layout = QHBoxLayout(header_bar)
        hb_layout.setContentsMargins(0, 0, 0, 12)
        title_lbl = QLabel("Custom Names")
        title_lbl.setStyleSheet("color: #4CAF50; font-size: 15px; font-weight: bold;")
        hb_layout.addWidget(title_lbl)
        hb_layout.addStretch()
        main_layout.addWidget(header_bar)

        # ── Generate row ──────────────────────────────────────────────────
        gen_frame = QFrame()
        gen_frame.setStyleSheet("QFrame { background-color: #252526; border: 1px solid #3d3d3d; border-radius: 4px; }")
        gen_fl = QHBoxLayout(gen_frame)
        gen_fl.setContentsMargins(14, 10, 14, 10)
        gen_fl.setSpacing(10)

        gen_lbl = QLabel("GENERATE")
        gen_lbl.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        gen_fl.addWidget(gen_lbl)

        _sep = QFrame()
        _sep.setFrameShape(QFrame.Shape.VLine)
        _sep.setStyleSheet("background: #3d3d3d; border: none; max-width: 1px;")
        gen_fl.addWidget(_sep)

        language_combo = QComboBox()
        language_combo.addItems(["English", "Khmer", "Vietnamese", "Thai", "Chinese"])
        language_combo.setFixedWidth(140)
        language_combo.setFixedHeight(34)
        gen_fl.addWidget(language_combo)

        random_count_input = QLineEdit()
        random_count_input.setPlaceholderText("Amount (e.g. 50)")
        random_count_input.setFixedWidth(140)
        random_count_input.setFixedHeight(34)
        gen_fl.addWidget(random_count_input)

        gen_fl.addStretch()

        generate_btn = QPushButton("  Generate")
        generate_btn.setIcon(qta.icon('fa5s.magic', color='#ffffff'))
        generate_btn.setFixedHeight(34)
        generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: #ffffff;
                font-size: 12px; font-weight: bold;
                border: none; border-radius: 4px; padding: 0 16px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        gen_fl.addWidget(generate_btn)
        main_layout.addWidget(gen_frame)

        # ── Names columns ─────────────────────────────────────────────────
        names_layout = QHBoxLayout()
        names_layout.setSpacing(12)

        def _make_col(label_text):
            col = QVBoxLayout()
            col.setSpacing(6)
            hdr = QLabel(label_text)
            hdr.setStyleSheet("color: #4CAF50; font-size: 13px; font-weight: bold;")
            col.addWidget(hdr)
            te = QTextEdit()
            col.addWidget(te, 1)
            cnt = QLabel("0 name(s)")
            cnt.setStyleSheet("color: #555555; font-size: 11px;")
            col.addWidget(cnt)
            return col, te, cnt

        first_col, first_text_edit, first_count_label = _make_col("First Names")
        last_col,  last_text_edit,  last_count_label  = _make_col("Last Names")

        first_text_edit.setPlaceholderText("James\nKenneth\nJoseph\nAndrew")
        last_text_edit.setPlaceholderText("Lopez\nHall\nCampbell\nAllen")

        if self.first_name_input.text():
            first_text_edit.setPlainText(self.first_name_input.text().replace(", ", "\n"))
        if self.last_name_input.text():
            last_text_edit.setPlainText(self.last_name_input.text().replace(", ", "\n"))

        names_layout.addLayout(first_col, 1)

        col_div = QFrame()
        col_div.setFrameShape(QFrame.Shape.VLine)
        col_div.setStyleSheet("background: #3d3d3d; border: none; max-width: 1px;")
        names_layout.addWidget(col_div)

        names_layout.addLayout(last_col, 1)
        main_layout.addLayout(names_layout, 1)

        # ── Preview bar ───────────────────────────────────────────────────
        preview_label = QLabel("")
        preview_label.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(preview_label)

        def update_counts():
            first_names = [n.strip() for n in first_text_edit.toPlainText().split('\n') if n.strip()]
            last_names  = [n.strip() for n in last_text_edit.toPlainText().split('\n') if n.strip()]
            first_count_label.setText(f"{len(first_names)} name(s)")
            last_count_label.setText(f"{len(last_names)} name(s)")
            if first_names and last_names:
                accounts = len(first_names) * len(last_names)
                preview_label.setText(f"{accounts} combination(s)  —  {len(first_names)} first × {len(last_names)} last")
                preview_label.setStyleSheet("color: #4CAF50; font-size: 11px; background: transparent;")
            else:
                preview_label.setText("")
        
        first_text_edit.textChanged.connect(update_counts)
        last_text_edit.textChanged.connect(update_counts)
        update_counts()

        def generate_random_names():
            try:
                count = int(random_count_input.text().strip())
                if count <= 0 or count > 1000:
                    QMessageBox.warning(dialog, "Invalid Amount", "Please enter a number between 1 and 1000")
                    return
                
                import random
                language = language_combo.currentText()
                
                # Simple name lists for each language
                if language == "English":
                    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles",
                                 "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan", "Jessica", "Sarah", "Karen"]
                    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
                                "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
                elif language == "Khmer":
                    first_names = ["Sok", "Srey", "Chea", "Kosal", "Virak", "Dara", "Rith", "Vanna", "Sophea", "Bopha"]
                    last_names = ["Chan", "Chea", "Heng", "Kim", "Lay", "Mao", "Phan", "Sam", "Sok", "Tan"]
                elif language == "Vietnamese":
                    first_names = ["Anh", "Minh", "Hieu", "Linh", "Mai", "Nga", "Phong", "Quan", "Thanh", "Tuan"]
                    last_names = ["Nguyen", "Tran", "Le", "Pham", "Hoang", "Phan", "Vu", "Vo", "Dang", "Bui"]
                elif language == "Thai":
                    first_names = ["Somchai", "Somsak", "Sombat", "Suchada", "Sumalee", "Thida", "Wanida", "Yupa", "Anuwat", "Chaiwat"]
                    last_names = ["Saetang", "Sangkaew", "Somboon", "Suwan", "Wattana", "Wongsa", "Chaiyaporn", "Kaewkham", "Rattanasiri", "Srisawat"]
                else:  # Chinese
                    first_names = ["Wei", "Ming", "Jun", "Jie", "Hao", "Li", "Fang", "Xiu", "Ying", "Mei"]
                    last_names = ["Wang", "Li", "Zhang", "Liu", "Chen", "Yang", "Huang", "Zhao", "Wu", "Zhou"]
                
                # Generate random names
                selected_first = random.sample(first_names * (count // len(first_names) + 1), count)
                selected_last = random.sample(last_names * (count // len(last_names) + 1), count)
                
                first_text_edit.setPlainText("\n".join(selected_first))
                last_text_edit.setPlainText("\n".join(selected_last))
                
            except ValueError:
                QMessageBox.warning(dialog, "Invalid Input", "Please enter a valid number")
        
        generate_btn.clicked.connect(generate_random_names)

        # ── Bottom buttons ────────────────────────────────────────────────
        _div2 = QFrame()
        _div2.setFrameShape(QFrame.Shape.HLine)
        _div2.setStyleSheet("background: #3d3d3d; border: none; max-height: 1px;")
        main_layout.addWidget(_div2)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        clear_names_btn = QPushButton("  Clear All")
        clear_names_btn.setIcon(qta.icon('fa5s.trash-alt', color='#888888'))
        clear_names_btn.setFixedHeight(36)
        clear_names_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #888888;
                border: 1px solid #3d3d3d; border-radius: 4px;
                font-size: 12px; padding: 0 14px;
            }
            QPushButton:hover { border-color: #f44336; color: #f44336; background-color: #2d2d2d; }
        """)
        def clear_all_names():
            first_text_edit.clear()
            last_text_edit.clear()
        clear_names_btn.clicked.connect(clear_all_names)
        btn_layout.addWidget(clear_names_btn)

        btn_layout.addStretch()

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
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("  Save Names")
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
        save_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(save_btn)

        main_layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Save first names
            first_names = [name.strip() for name in first_text_edit.toPlainText().split('\n') if name.strip()]
            self.first_name_input.setText(", ".join(first_names))
            
            # Save last names
            last_names = [name.strip() for name in last_text_edit.toPlainText().split('\n') if name.strip()]
            self.last_name_input.setText(", ".join(last_names))
            
            # Update display
            self.update_names_display()
    

    def browse_profile_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Profile Pictures Folder")
        if folder:
            self.profile_pic_input.setText(folder)
    

    def update_email_display(self):
        """Update the email display field based on current values."""
        email_list = self.email_list_input.text()
        single_email = self.email_input.text()
        
        if email_list:
            # Multiple emails mode
            emails = [e.strip() for e in email_list.split(',') if e.strip()]
            if len(emails) > 1:
                display_text = f"{emails[0]}, ... ({len(emails)} emails)"
            else:
                display_text = emails[0] if emails else "No emails"
        else:
            # Single email mode
            display_text = single_email if single_email else "testuser@example.com"
        
        self.email_display.setText(display_text)
    

    def edit_multiple_emails(self):
        """Open dialog to edit multiple emails."""
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_edit_emails"))
        dialog.setFixedSize(500, 400)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #e0e0e0;
            }
            QLabel {
                color: #b0b0b0;
                font-size: 12px;
            }
            QTextEdit {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 0px;
                color: #e0e0e0;
                font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', 'Courier New', monospace;
                font-size: 13px;
                padding: 10px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 0px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Configure Multiple Emails")
        title.setStyleSheet("color: #4CAF50; font-weight: 600; font-size: 15px; margin-bottom: 5px;")
        main_layout.addWidget(title)
        
        # Description
        desc = QLabel("Enter email addresses (one per line). Each email will be used for one account.")
        desc.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 10px;")
        main_layout.addWidget(desc)
        
        # Email text edit
        email_label = QLabel("Email Addresses:")
        email_label.setStyleSheet("color: #4CAF50; font-weight: 600; font-size: 13px;")
        main_layout.addWidget(email_label)
        
        email_text_edit = QTextEdit()
        
        # Load current emails
        if self.email_list_input.text():
            current_emails = self.email_list_input.text().replace(", ", "\n")
        else:
            current_emails = self.email_input.text()
        
        email_text_edit.setPlainText(current_emails)
        email_text_edit.setPlaceholderText("user1@example.com\nuser2@example.com\nuser3@example.com")
        main_layout.addWidget(email_text_edit)
        
        # Preview label
        preview_label = QLabel("")
        preview_label.setStyleSheet("color: #00bcd4; font-size: 11px; margin-top: 5px;")
        main_layout.addWidget(preview_label)
        
        def update_preview():
            emails = [e.strip() for e in email_text_edit.toPlainText().split('\n') if e.strip()]
            preview_label.setText(f"💡 {len(emails)} email(s) configured")
        
        # Connect text changes to preview update
        email_text_edit.textChanged.connect(update_preview)
        update_preview()  # Initial preview
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #555555;")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Emails")
        save_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(save_btn)
        
        main_layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Save emails
            emails = [email.strip() for email in email_text_edit.toPlainText().split('\n') if email.strip()]
            
            if len(emails) > 1:
                # Multiple emails mode
                self.email_list_input.setText(", ".join(emails))
                self.email_input.setText(emails[0])  # Store first as default
            elif len(emails) == 1:
                # Single email mode
                self.email_list_input.setText("")
                self.email_input.setText(emails[0])
            else:
                # No emails
                self.email_list_input.setText("")
                self.email_input.setText("testuser@example.com")
            
            # Update display
            self.update_email_display()
    

    def open_verification_dialog(self):
        """Open dialog to configure verification methods."""
        dialog = QDialog(self)
        dialog.setWindowTitle(_T("dlg_verification"))
        dialog.setFixedSize(400, 350)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
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
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Select Verification Methods")
        title.setStyleSheet("color: #FF9800; font-size: 15px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel("Choose which verification methods to support during registration:")
        desc.setStyleSheet("color: #888888; font-size: 12px; margin-bottom: 5px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Checkboxes
        checkboxes = {}
        verification_methods = [
            ("auto_detect", "Auto Detect"),
            ("sms_code", "SMS Code"),
            ("email_code", "Email Code"),
            ("2fa_auth", "2FA Authenticator"),
            ("backup_codes", "Backup Codes"),
            ("security_questions", "Security Questions")
        ]
        
        for method_id, method_name in verification_methods:
            checkbox = QCheckBox(method_name)
            checkbox.setChecked(self.verification_methods.get(method_id, False))
            checkbox.setStyleSheet("""
                QCheckBox {
                    color: #e0e0e0;
                    font-size: 13px;
                    spacing: 10px;
                    padding: 5px;
                }
                QCheckBox::indicator {
                    width: 20px;
                    height: 20px;
                    border-radius: 0px;
                    border: 2px solid #3a3a3a;
                    background-color: #2a2a2a;
                }
                QCheckBox::indicator:checked {
                    background-color: #FF9800;
                    border: 2px solid #FF9800;
                }
                QCheckBox:hover {
                    color: #FF9800;
                }
            """)
            checkboxes[method_id] = checkbox
            layout.addWidget(checkbox)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update verification methods
            for method_id, checkbox in checkboxes.items():
                self.verification_methods[method_id] = checkbox.isChecked()
            
            # Update status label
            selected_count = sum(1 for v in self.verification_methods.values() if v)
            # TODO: Create verification_status_label in UI if needed
            # self.verification_status_label.setText(f"{selected_count} method{'s' if selected_count != 1 else ''} selected")
    

    def generate_account_data(self, first_names_list, last_names_list, base_email, password, base_birthday, gender, phone):
        """Generate account data from name lists."""
        import random
        from datetime import datetime, timedelta
        
        accounts = []
        
        # Parse name lists
        first_names = [name.strip() for name in first_names_list.split(',') if name.strip()]
        last_names = [name.strip() for name in last_names_list.split(',') if name.strip()]
        
        if not first_names or not last_names:
            return []
        
        # Check if multiple emails are configured
        email_list_text = self.email_list_input.text()
        if email_list_text:
            # Multiple emails mode - use list of emails
            email_list = [e.strip() for e in email_list_text.split(',') if e.strip()]
        else:
            # Single email mode - will add index
            email_list = []
        
        # Check if random phone is enabled
        use_random_phone = self.random_phone_checkbox.isChecked()
        
        # Check if random password is enabled
        use_random_password = self.random_password_checkbox.isChecked()
        
        # Check if Reg Novary (No Variation) is enabled
        use_reg_novary = self.reg_novary_checkbox.isChecked()
        
        # Create 1:1 pairing of first and last names (not all combinations)
        account_index = 1
        email_index = 0  # Track which email from list to use
        
        # Check if using email or phone
        use_email = self.use_email_checkbox.isChecked()
        
        # Pair names 1:1 instead of all combinations
        num_accounts = min(len(first_names), len(last_names))
        
        for i in range(num_accounts):
            first_name = first_names[i]
            last_name = last_names[i]
            
            # Email handling
            if not use_email:
                # Using phone number - no email needed
                email = ""
            elif email_list:
                # Multiple emails mode - use from list
                if email_index < len(email_list):
                    email = email_list[email_index]
                    email_index += 1
                else:
                    # If we run out of emails, stop creating accounts
                    break
            elif use_reg_novary:
                # No variation - use exact email
                email = base_email
            else:
                # Add index variation
                if '@' in base_email:
                    email_parts = base_email.split('@')
                    email = f"{email_parts[0]}{account_index}@{email_parts[1]}"
                else:
                    email = f"{base_email}{account_index}"
            
            # Birthday variation
            if use_reg_novary:
                # No variation - use exact birthday
                birthday = base_birthday
            else:
                # Randomize day within same month/year
                try:
                    day, month, year = base_birthday.split("/")
                    base_day = int(day)
                    # Randomize day ±5 days
                    new_day = max(1, min(28, base_day + random.randint(-5, 5)))
                    birthday = f"{new_day:02d}/{month}/{year}"
                except:
                    birthday = base_birthday
            
            # Gender handling - randomize if "Random" is selected
            if gender.lower() == "random":
                account_gender = random.choice(["Male", "Female"])
            else:
                account_gender = gender
            
            # Phone handling - generate random if enabled
            if use_random_phone:
                account_phone = self.generate_random_phone()
            else:
                account_phone = phone
            
            # Password handling - generate random if enabled
            if use_random_password:
                account_password = self.generate_random_password()
            else:
                account_password = password
            
            accounts.append({
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'password': account_password,
                'birthday': birthday,
                'gender': account_gender,
                'phone': account_phone
            })
            
            account_index += 1
        
        return accounts
    

    def get_selected_devices(self):
        """Get list of selected device IDs."""
        selected = []
        
        # First check if auto reg device select exists and has selections
        if hasattr(self, 'auto_reg_device_select'):
            rows = self.auto_reg_device_select.selectionModel().selectedRows()
            for idx in rows:
                item = self.auto_reg_device_select.item(idx.row(), 0)
                if item:
                    text = item.text()
                    device_id = text.split('. ', 1)[-1].strip()
                    selected.append(device_id)
        
        # If no devices selected from auto reg list, fall back to checkboxes
        if not selected:
            for cb in self.device_checkboxes:
                if cb.isChecked():
                    selected.append(cb.text())
        
        return selected
    

    def get_action_delay(self):
        """Get the configured action delay in seconds."""
        try:
            delay = float(self.delay_input.text())
            # Clamp between 0.5 and 10.0 seconds
            return max(0.5, min(10.0, delay))
        except (ValueError, AttributeError):
            return 2.0  # Default delay
    

    def get_safety_mode(self):
        """Check if safety mode is enabled."""
        try:
            return self.safety_mode_checkbox.isChecked()
        except AttributeError:
            return True  # Default to safe mode


    def open_auto_registration_tab(self):
        """Open a new dynamic Auto Registration tab"""
        # Check if tab already exists
        for i in range(self.tab_widget.count()):
            if "Auto Registration" in self.tab_widget.tabText(i):
                self.tab_widget.setCurrentIndex(i)
                return
        
        # Create new tab - Professional web-app style like Login tab
        auto_reg_tab = QWidget()
        auto_reg_tab.setStyleSheet("background-color: #0f0f0f;")
        auto_reg_main_layout = QHBoxLayout(auto_reg_tab)
        auto_reg_main_layout.setSpacing(0)
        auto_reg_main_layout.setContentsMargins(0, 0, 0, 0)
        
        # ── Left Panel: Created Accounts Table (65% width) ─────────────────
        left_panel = QFrame()
        left_panel.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-right: 1px solid #3d3d3d; }")
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
        left_title = QLabel("Created Accounts")
        left_title.setStyleSheet("color: #4CAF50; font-size: 15px; font-weight: bold; background: transparent;")
        left_toolbar_layout.addWidget(left_title)
        
        self.ar_account_count_badge = QLabel("0 accounts")
        self.ar_account_count_badge.setStyleSheet("QLabel { background-color: transparent; color: #444444; font-size: 11px; font-weight: 500; padding: 0px; border: none; }")
        left_toolbar_layout.addWidget(self.ar_account_count_badge)
        left_toolbar_layout.addStretch()
        
        left_layout.addWidget(left_toolbar)
        
        # Accounts Table
        self.accounts_table = QTableWidget()
        self.accounts_table.setColumnCount(8)
        self.accounts_table.setHorizontalHeaderLabels([
            "Email", "Password", "Name", "DOB", "Gender", "Device", "Status", "Created"
        ])
        
        # Modern table styling
        self.accounts_table.setStyleSheet("""
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
        
        # Set column widths
        header = self.accounts_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Email
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Password
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Name
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # DOB
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Gender
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Device
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Status
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Created
        header.setHighlightSections(False)
        
        # Set row height
        self.accounts_table.verticalHeader().setDefaultSectionSize(40)
        self.accounts_table.verticalHeader().setVisible(False)
        
        # Enable row selection
        self.accounts_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.accounts_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.accounts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        left_layout.addWidget(self.accounts_table)
        
        # Bottom stats bar
        left_stats_bar = QFrame()
        left_stats_bar.setFixedHeight(40)
        left_stats_bar.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-top: 1px solid #3d3d3d; }")
        left_stats_layout = QHBoxLayout(left_stats_bar)
        left_stats_layout.setContentsMargins(20, 0, 20, 0)
        left_stats_layout.setSpacing(20)
        
        self._ar_stat_total = QLabel("Total: 0")
        self._ar_stat_done  = QLabel("Done: 0")
        self._ar_stat_fail  = QLabel("Failed: 0")
        self.ar_time_label = QLabel("Time: 0s")
        for _lbl, _col in [(self._ar_stat_total, "#555555"), (self._ar_stat_done, "#4CAF50"), (self._ar_stat_fail, "#f44336"), (self.ar_time_label, "#FF9800")]:
            _lbl.setStyleSheet(f"color: {_col}; font-size: 11px; font-weight: 500; background: transparent;")
            left_stats_layout.addWidget(_lbl)
        left_stats_layout.addStretch()
        left_layout.addWidget(left_stats_bar)
        
        auto_reg_main_layout.addWidget(left_panel, 65)
        
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
        self.auto_reg_device_count_label = QLabel("0 device(s)")
        self.auto_reg_device_count_label.setStyleSheet("QLabel { background: transparent; color: #4CAF50; font-size: 13px; font-weight: 500; padding: 0; border: none; }")
        right_top_bar_layout.addWidget(self.auto_reg_device_count_label)
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
        
        # Helper for labels
        def _slabel(text):
            l = QLabel(text)
            l.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; background: transparent; padding: 6px 0 4px 0;")
            return l
        
        _input_style = """
            QLineEdit, QComboBox {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 8px 12px;
                color: #e0e0e0;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #4CAF50;
            }
        """
        
        # Hidden names fields (moved to Advanced Settings)
        self.names_display = QLineEdit()
        self.names_display.setReadOnly(True)
        self.names_display.setVisible(False)
        
        self.first_name_input = QLineEdit()
        self.first_name_input.setText("")
        self.first_name_input.setVisible(False)
        
        self.last_name_input = QLineEdit()
        self.last_name_input.setText("")
        self.last_name_input.setVisible(False)
        
        # Hidden Auto English Names checkbox (moved to Advanced Settings)
        self.auto_english_names_checkbox = QCheckBox("Auto English Names (Random)")
        self.auto_english_names_checkbox.setVisible(False)
        self.auto_english_names_checkbox.stateChanged.connect(self.toggle_auto_names)
        
        # Hidden checkboxes for email/phone (controlled from Advanced Settings)
        self.use_email_checkbox = QCheckBox()
        self.use_email_checkbox.setChecked(True)
        self.use_email_checkbox.setVisible(False)
        self.use_email_checkbox.stateChanged.connect(self.toggle_signup_method)
        
        self.use_phone_checkbox = QCheckBox()
        self.use_phone_checkbox.setChecked(False)
        self.use_phone_checkbox.setVisible(False)
        self.use_phone_checkbox.stateChanged.connect(self.toggle_signup_method)
        
        # Hidden email fields (moved to Advanced Settings)
        self.email_display = QLineEdit()
        self.email_display.setReadOnly(True)
        self.email_display.setVisible(False)
        
        self.email_input = QLineEdit()
        self.email_input.setText("")
        self.email_input.setVisible(False)
        
        self.email_list_input = QLineEdit()
        self.email_list_input.setText("")
        self.email_list_input.setVisible(False)
        
        # Hidden password fields (moved to Advanced Settings)
        self.password_input = QLineEdit()
        self.password_input.setText("SecurePass123!")
        self.password_input.setVisible(False)
        
        self.random_password_checkbox = QCheckBox("Random")
        self.random_password_checkbox.setChecked(False)
        self.random_password_checkbox.setVisible(False)
        
        # Device selection container (matching Login tab exactly)
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
        
        # Device list
        self.auto_reg_device_select = QTableWidget()
        self.auto_reg_device_select.setColumnCount(3)
        self.auto_reg_device_select.setHorizontalHeaderLabels(["Device", "Proxy", "Device Changer"])
        self.auto_reg_device_select.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.auto_reg_device_select.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.auto_reg_device_select.verticalHeader().setVisible(False)
        self.auto_reg_device_select.setShowGrid(False)
        self.auto_reg_device_select.horizontalHeader().setStretchLastSection(True)
        self.auto_reg_device_select.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.auto_reg_device_select.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.auto_reg_device_select.setStyleSheet("""
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
        self.auto_reg_device_select.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Connect context menu for MaxChange integration
        self.auto_reg_device_select.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.auto_reg_device_select.customContextMenuRequested.connect(self.show_auto_reg_device_context_menu)
        
        device_container_layout.addWidget(self.auto_reg_device_select)
        
        device_container.setFixedHeight(280)
        dev_row = QHBoxLayout()
        dev_row.addWidget(device_container)
        rc.addLayout(dev_row)
        
        # Hidden fields for advanced settings
        self.birthday_input = QLineEdit()
        self.birthday_input.setText("15/06/1995")
        self.birthday_input.setVisible(False)
        
        self.gender_input = QComboBox()
        self.gender_input.addItems(["Male", "Female", "Custom", "Random"])
        self.gender_input.setCurrentText("Male")
        self.gender_input.setVisible(False)
        
        self.phone_input = QLineEdit()
        self.phone_input.setVisible(False)
        
        self.random_phone_checkbox = QCheckBox()
        self.random_phone_checkbox.setChecked(False)
        self.random_phone_checkbox.setVisible(False)
        
        self.country_code_input = QComboBox()
        self.country_code_input.addItems([
            "+1 (US/Canada)", "+44 (UK)", "+855 (Cambodia)", "+84 (Vietnam)",
            "+86 (China)", "+91 (India)", "+62 (Indonesia)", "+63 (Philippines)",
            "+66 (Thailand)", "+60 (Malaysia)", "+81 (Japan)", "+82 (South Korea)",
            "+65 (Singapore)", "+61 (Australia)"
        ])
        self.country_code_input.setCurrentText("+1 (US/Canada)")
        self.country_code_input.setVisible(False)
        
        self.profile_pic_input = QLineEdit()
        self.profile_pic_input.setVisible(False)
        
        self.reg_novary_checkbox = QCheckBox()
        self.reg_novary_checkbox.setChecked(False)
        self.reg_novary_checkbox.setVisible(False)
        
        self.verification_checkbox = QCheckBox()
        self.verification_checkbox.setChecked(False)
        self.verification_checkbox.setVisible(False)
        
        # Initialize verification methods dictionary
        self.verification_methods = {
            "auto_detect": True,
            "sms_code": False,
            "email_code": False,
            "2fa_auth": False,
            "backup_codes": False,
            "security_questions": False
        }
        
        rc.addSpacing(12)
        
        # Advanced Settings Button
        advanced_btn = QPushButton("  Advanced Settings")
        advanced_btn.setIcon(qta.icon('fa5s.cog', color='#888888'))
        advanced_btn.setFixedHeight(36)
        advanced_btn.setStyleSheet("""
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
        advanced_btn.clicked.connect(self.open_auto_reg_advanced_settings)
        rc.addWidget(advanced_btn)
        
        rc.addStretch()
        
        # Control Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.start_btn = QPushButton(" START")
        self.start_btn.setIcon(qta.icon('fa5s.play', color='#ffffff'))
        self.start_btn.setFixedHeight(44)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 13px;
                font-weight: 600;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #555555;
            }
        """)
        self.start_btn.clicked.connect(self.start_registration)
        btn_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton(" STOP")
        self.stop_btn.setIcon(qta.icon('fa5s.stop', color='#ffffff'))
        self.stop_btn.setFixedHeight(44)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-size: 13px;
                font-weight: 600;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #555555;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_registration)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)
        
        rc.addLayout(btn_layout)
        
        right_scroll.setWidget(right_content)
        right_layout.addWidget(right_scroll)
        
        auto_reg_main_layout.addWidget(right_panel, 35)
        
        # Add tab
        index = self.tab_widget.addTab(auto_reg_tab, "Auto Registration")
        self.tab_widget.setCurrentIndex(index)
        
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
        close_btn.clicked.connect(lambda checked, w=auto_reg_tab: self.close_dynamic_tab_by_widget(w))
        
        self.tab_widget.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, close_btn)

        # Load devices into the device table now that the tab and widget exist
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.load_auto_reg_devices)


    def close_dynamic_tab_by_widget(self, widget):
        """Close tab by widget reference"""
        index = self.tab_widget.indexOf(widget)
        if index >= 3:
            self.tab_widget.removeTab(index)
    

    def close_dynamic_tab(self, index):
        """Close dynamic tabs (but not the main tabs)"""
        if index >= 3:  # Only close tabs after the 3 main tabs
            self.tab_widget.removeTab(index)
    

    def load_auto_reg_devices(self):
        """Load connected devices into the auto reg device table"""
        import threading, tempfile
        
        # Show loading message
        if hasattr(self, 'auto_reg_device_count_label'):
            self.auto_reg_device_count_label.setText("Scanning...")
        
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

                # Use cached device list first (populated by refresh_devices)
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

                # Fallback: live ADB scan (the slow part - runs in background)
                if not device_ids:
                    result = safe_subprocess_run([self.adb_path, "devices"], capture_output=True, text=True, timeout=10)
                    for line in result.stdout.strip().split('\n')[1:]:
                        if '\t' in line:
                            did, status = line.split('\t', 1)
                            if status.strip() == 'device':
                                device_ids.append(did.strip())

                # Build device list with proxy/spoof info
                devices = []
                for device_id in device_ids:
                    proxy = proxy_cache.get(device_id, '—')
                    spoof = spoof_cache.get(device_id, '—')
                    devices.append((device_id, proxy, spoof))

                # Emit signal with device data
                self._auto_reg_devices_signal.emit(devices)
                
            except Exception as e:
                print(f"Error scanning auto reg devices: {e}")
                self._auto_reg_devices_signal.emit([])  # Empty list on error
        
        # Start background thread
        threading.Thread(target=_scan, daemon=True).start()
    
    
    def _apply_auto_reg_devices(self, devices):
        """Apply device list to auto reg table (runs on main thread via signal)"""
        try:
            if not hasattr(self, 'auto_reg_device_select'):
                return
            
            # Clear table
            self.auto_reg_device_select.setRowCount(0)
            
            # Populate table
            for idx, (device_id, proxy, spoof) in enumerate(devices):
                row = self.auto_reg_device_select.rowCount()
                self.auto_reg_device_select.insertRow(row)
                self.auto_reg_device_select.setRowHeight(row, 32)
                
                d_item = QTableWidgetItem(f"{idx+1}. {device_id}")
                d_item.setForeground(QColor("#4CAF50"))
                p_item = QTableWidgetItem(proxy)
                p_item.setForeground(QColor("#FF9800") if proxy != '—' else QColor("#888888"))
                s_item = QTableWidgetItem(spoof)
                s_item.setForeground(QColor("#FF9800") if spoof != '—' else QColor("#888888"))
                
                for col, item in enumerate([d_item, p_item, s_item]):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self.auto_reg_device_select.setItem(row, col, item)

            # Update count label
            if hasattr(self, 'auto_reg_device_count_label'):
                self.auto_reg_device_count_label.setText(f"{len(devices)} device(s)")
                
        except Exception as e:
            print(f"Error applying auto reg devices: {e}")


    def show_auto_reg_device_context_menu(self, position):
        """Show context menu for Auto Reg device list"""
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 4px;
                font-size: 12px;
            }
            QMenu::item {
                padding: 8px 20px 8px 12px;
                border-radius: 4px;
                margin: 1px 2px;
            }
            QMenu::item:selected {
                background-color: rgba(76,175,80,0.2);
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3d3d3d;
                margin: 4px 8px;
            }
            QMenu::icon {
                padding-left: 4px;
            }
        """)
        
        # Select All
        select_all_action = menu.addAction(qta.icon('fa5s.check-square', color='#4CAF50'), "Select All")
        
        # Load Devices
        load_devices_action = menu.addAction(qta.icon('fa5s.sync', color='#4CAF50'), "Load Devices")
        
        menu.addSeparator()
        
        # MaxChange submenu
        maxchange_menu = menu.addMenu(qta.icon('fa5s.magic', color='#FF9800'), "MaxChange Device Spoofer")
        maxchange_menu.setStyleSheet(menu.styleSheet())  # Apply same style
        
        mc_change_action = maxchange_menu.addAction(qta.icon('fa5s.random', color='#FF9800'), "Change Device (Random)")
        mc_samsung_action = maxchange_menu.addAction(qta.icon('fa5b.android', color='#888888'), "Change Device (Samsung)")
        mc_oneplus_action = maxchange_menu.addAction(qta.icon('fa5b.android', color='#888888'), "Change Device (OnePlus)")
        mc_xiaomi_action = maxchange_menu.addAction(qta.icon('fa5b.android', color='#888888'), "Change Device (Xiaomi)")
        mc_google_action = maxchange_menu.addAction(qta.icon('fa5b.android', color='#888888'), "Change Device (Google)")
        maxchange_menu.addSeparator()
        mc_check_action = maxchange_menu.addAction(qta.icon('fa5s.info-circle', color='#2196F3'), "Check Current Device")
        
        menu.addSeparator()
        
        # Copy submenu
        copy_menu = menu.addMenu(qta.icon('fa5s.copy', color='#2196F3'), "Copy")
        copy_device_id_action = copy_menu.addAction(qta.icon('fa5s.mobile-alt', color='#888888'), "Device ID")
        copy_all_ids_action = copy_menu.addAction(qta.icon('fa5s.list', color='#888888'), "All Device IDs")

        menu.addSeparator()

        # Device actions
        clear_recents_action = menu.addAction(qta.icon('fa5s.broom', color='#FF5722'), "Clear Recents")

        # Execute menu
        action = menu.exec(self.auto_reg_device_select.viewport().mapToGlobal(position))

        if action == select_all_action:
            self.auto_reg_device_select.selectAll()
        elif action == load_devices_action:
            self._refresh_all_devices()
        elif action == mc_change_action:
            self._maxchange_change_device(brand_filter=None)
        elif action == mc_samsung_action:
            self._maxchange_change_device(brand_filter="Samsung")
        elif action == mc_oneplus_action:
            self._maxchange_change_device(brand_filter="OnePlus")
        elif action == mc_xiaomi_action:
            self._maxchange_change_device(brand_filter="Xiaomi")
        elif action == mc_google_action:
            self._maxchange_change_device(brand_filter="Google")
        elif action == mc_check_action:
            self._maxchange_check_device()
        elif action == copy_device_id_action:
            rows = self.auto_reg_device_select.selectionModel().selectedRows()
            device_ids = [self.auto_reg_device_select.item(r.row(), 0).text().split('. ', 1)[-1].strip()
                         for r in rows if self.auto_reg_device_select.item(r.row(), 0)]
            if device_ids:
                QApplication.clipboard().setText('\n'.join(device_ids))
                self.add_activity(f"Copied {len(device_ids)} device ID(s) to clipboard")
        elif action == clear_recents_action:
            rows = self.auto_reg_device_select.selectionModel().selectedRows()
            for r in rows:
                item = self.auto_reg_device_select.item(r.row(), 0)
                if item:
                    self._clear_recents_single(item.text().split('. ', 1)[-1].strip())

    

    def _apply_maxchange_professional(self, device_id, brand_filter=None):
        """
        Apply professional MaxChange spoofing with PushFile mode support.
        This uses the same logic as FacebookRegistration.apply_maxchange_spoofing()
        but works standalone without creating a full registration instance.
        Returns the fake device model string or empty string on failure.
        
        NOTE: MaxChange changes require a REBOOT to take effect in system properties!
        """
        import random
        MAXCHANGE_PKG = "com.minsoftware.maxchanger"
        adb_path = "C:\\Users\\KLS COMPUTER\\Desktop\\FRT\\platform-tools\\adb.exe"
        base_dir = _PROJECT_ROOT
        maxchanger_dir = os.path.join(base_dir, "maxchanger")
        
        def adb_shell(cmd):
            """Execute ADB shell command."""
            try:
                result = subprocess.run(
                    f'"{adb_path}" -s {device_id} shell {cmd}',
                    shell=True, capture_output=True, text=True, timeout=30
                )
                return result.stdout.strip()
            except:
                return ""
        
        def adb_push(local_path, remote_path):
            """Push file to device."""
            try:
                cmd = f'"{adb_path}" -s {device_id} push "{local_path}" "{remote_path}"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
                return "pushed" in result.stdout.lower() or result.returncode == 0
            except:
                return False
        
        def mc_get_device_name():
            """Read fake device fingerprint from MaxChange Device.xml."""
            xml_text = adb_shell('su -c "cat /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml"')
            if xml_text:
                try:
                    import re
                    fp_match = re.search(r'name="fingerprint"[^>]*>([^<]+)<', xml_text)
                    tc_match = re.search(r'name="time_check"[^>]*>([^<]+)<', xml_text)
                    if fp_match and tc_match and fp_match.group(1) and tc_match.group(1):
                        return fp_match.group(1) + tc_match.group(1)
                except:
                    pass
            return ""
        
        def mc_get_model_from_xml():
            """Read the fake model/brand from MaxChange Device.xml."""
            xml_text = adb_shell('su -c "cat /data/data/com.minsoftware.maxchanger/shared_prefs/Device.xml"')
            if not xml_text:
                return ""
            try:
                import re
                brand_m = re.search(r'name="brand"[^>]*>([^<]+)<', xml_text)
                model_m = re.search(r'name="model"[^>]*>([^<]+)<', xml_text)
                brand = brand_m.group(1).strip() if brand_m else ""
                model = model_m.group(1).strip() if model_m else ""
                if brand and model:
                    return f"{brand} {model}"
                if model:
                    return model
                if brand:
                    return brand
            except:
                pass
            return ""
        
        def mc_push_file_info(profile_name):
            """Push a .tar.gz profile to MaxChange data directory (PushFile mode)."""
            if not profile_name:
                return False
            
            local_file = os.path.join(maxchanger_dir, f"{profile_name}.tar.gz")
            if not os.path.exists(local_file):
                self.add_activity(f"⚠️ {device_id}: Profile {profile_name}.tar.gz not found")
                return False
            
            # Clear MaxChange data and grant permissions
            adb_shell(f"pm clear {MAXCHANGE_PKG}")
            adb_shell(f"pm grant {MAXCHANGE_PKG} android.permission.READ_EXTERNAL_STORAGE")
            adb_shell(f"pm grant {MAXCHANGE_PKG} android.permission.WRITE_EXTERNAL_STORAGE")
            
            tar_filename = f"{profile_name}.tar.gz"
            mc_data = f"/data/data/{MAXCHANGE_PKG}"
            
            for i in range(10):
                self.add_activity(f"📦 {device_id}: PushFile attempt {i + 1}/10...")
                
                # Push .tar.gz to /sdcard
                if not adb_push(local_file, f"/sdcard/{tar_filename}"):
                    time.sleep(2)
                    continue
                
                # Copy to MaxChange data dir via su
                adb_shell(f'su -c "cp /sdcard/{tar_filename} {mc_data}/{tar_filename}"')
                
                # Extract tar.gz inside the data dir
                adb_shell(f'su -c "tar -xzvf {mc_data}/{tar_filename} -C {mc_data}"')
                
                # Get the owner:group of the MaxChange data directory
                owner_group = adb_shell(
                    'su -c "ls -l /data/data | grep com.minsoftware.maxchanger | awk \'{print $3\":\"$4}\'"'
                ).strip()
                
                if not owner_group:
                    time.sleep(2)
                    continue
                
                # chown the entire data directory to the correct owner
                adb_shell(f'su -c "chown -R {owner_group} {mc_data}"')
                
                # Clean up /sdcard copy
                adb_shell(f'su -c "rm -r /sdcard/{tar_filename}"')
                
                self.add_activity(f"✅ {device_id}: PushFile success (owner={owner_group})")
                return True
            
            self.add_activity(f"❌ {device_id}: PushFile failed after 10 attempts")
            return False
        
        def mc_change_device_broadcast():
            """Change device via broadcast intent (fallback method)."""
            # Clear data and grant permissions
            adb_shell(f"pm clear {MAXCHANGE_PKG}")
            adb_shell(f"pm grant {MAXCHANGE_PKG} android.permission.READ_EXTERNAL_STORAGE")
            adb_shell(f"pm grant {MAXCHANGE_PKG} android.permission.WRITE_EXTERNAL_STORAGE")
            
            # Get old fingerprint
            old_name = mc_get_device_name()
            
            # Open MaxChange app
            self.add_activity(f"📱 {device_id}: Opening MaxChange app...")
            adb_shell("monkey -p com.minsoftware.maxchanger -c android.intent.category.LAUNCHER 1")
            time.sleep(3)
            
            # Try to change device (max 10 attempts for brand filtering)
            for attempt in range(1, 11):
                cmd = 'am broadcast -a com.minsoftware.maxchanger.CHANGE -n com.minsoftware.maxchanger/.AdbCaller'
                if brand_filter and brand_filter != "Random":
                    brands = [b.strip() for b in brand_filter.split("|") if b.strip()]
                    if brands:
                        chosen_brand = random.choice(brands)
                        cmd = f'am broadcast -a com.minsoftware.maxchanger.CHANGE --es "brand" "{chosen_brand}" -n com.minsoftware.maxchanger/.AdbCaller'
                
                result = adb_shell(cmd)
                if "Broadcast completed" in result:
                    time.sleep(2)
                    new_name = mc_get_device_name()
                    if new_name and new_name != old_name:
                        self.add_activity(f"✅ {device_id}: Broadcast change successful")
                        return True
                
                time.sleep(2)
            
            return False
        
        try:
            # Step 1: Ensure MaxChange is installed
            check = adb_shell(f"pm list packages {MAXCHANGE_PKG}")
            if MAXCHANGE_PKG not in check:
                self.add_activity(f"📦 {device_id}: Installing MaxChange...")
                for name in ["maxchange.apk", "maxchangev2.apk", "MaxChange.apk"]:
                    apk_path = os.path.join(base_dir, "app", name)
                    if os.path.exists(apk_path):
                        subprocess.run(
                            f'"{adb_path}" -s {device_id} install -r "{apk_path}"',
                            shell=True, capture_output=True, timeout=60
                        )
                        time.sleep(2)
                        break
            
            # Step 2: Choose profile and change strategy
            profile_name = None
            if os.path.exists(maxchanger_dir):
                tar_files = [f for f in os.listdir(maxchanger_dir) if f.endswith(".tar.gz")]
                if tar_files:
                    chosen_file = random.choice(tar_files)
                    profile_name = chosen_file.replace(".tar.gz", "")
                    self.add_activity(f"📁 {device_id}: Selected profile: {profile_name}")
            
            # Step 3: Execute device change
            success = False
            if profile_name:
                # Try PushFile mode first (professional mode with full device profiles)
                self.add_activity(f"🔧 {device_id}: Using PushFile mode (professional)...")
                if mc_push_file_info(profile_name):
                    # Verify the push worked
                    name = mc_get_device_name()
                    if name:
                        success = True
                        self.add_activity(f"✅ {device_id}: PushFile verified")
                
                # Fallback to broadcast if PushFile failed
                if not success:
                    self.add_activity(f"⚠️ {device_id}: PushFile failed, trying broadcast...")
                    success = mc_change_device_broadcast()
            else:
                # No profiles available - use broadcast only
                self.add_activity(f"⚠️ {device_id}: No profiles in maxchanger/, using broadcast...")
                success = mc_change_device_broadcast()
            
            # Step 4: Report result and prompt for reboot
            if success:
                fake_model = mc_get_model_from_xml()
                if not fake_model:
                    fake_model = adb_shell("getprop ro.product.model").strip()
                
                # Important: Inform user that reboot is required
                self.add_activity(f"⚠️ {device_id}: REBOOT REQUIRED for changes to take effect!")
                self.add_activity(f"💡 {device_id}: Device Info HW will show fake device name after reboot")
                
                return fake_model
            else:
                return ""
            
        except Exception as e:
            self.add_activity(f"❌ {device_id}: Exception - {str(e)[:100]}")
            return ""
    

    def _maxchange_change_device(self, brand_filter=None):
        """Apply MaxChange device spoofing to selected devices using professional PushFile mode (background thread)."""
        rows = self.auto_reg_device_select.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "No Device Selected", "Please select at least one device from the list.")
            return
        device_ids = [self.auto_reg_device_select.item(r.row(), 0).text().split('. ', 1)[-1].strip()
                     for r in rows if self.auto_reg_device_select.item(r.row(), 0)]
        if not device_ids:
            return
        
        brand_name = brand_filter if brand_filter else "Random"
        self.add_activity(f"🔄 Starting MaxChange ({brand_name}) for {len(device_ids)} device(s) - Fast Broadcast Mode...")
        
        # Create and start worker thread
        adb_path = "C:\\Users\\KLS COMPUTER\\Desktop\\FRT\\platform-tools\\adb.exe"
        base_dir = _PROJECT_ROOT
        
        from src.workers.maxchange_worker import MaxChangeWorker as _MaxChangeWorker
        
        self._maxchange_worker = _MaxChangeWorker(device_ids, brand_filter, adb_path, base_dir)
        self._maxchange_worker.progress.connect(self.add_activity)
        self._maxchange_worker.finished.connect(self._on_maxchange_finished)
        self._maxchange_worker.spoof_updated.connect(self._update_spoof_in_table_ui)
        self._maxchange_worker.start()
    

    def _on_maxchange_finished(self, success_count, device_ids):
        """Handle MaxChange worker completion - show success dialog."""
        if success_count > 0:
            self.add_activity(f"✅ MaxChange complete: {success_count}/{len(device_ids)} device(s) changed")
            self.add_activity(f"⚠️ Reboot devices to apply changes")
            
            # Show success dialog
            QMessageBox.information(
                self, "MaxChange Complete",
                f"✅ Successfully changed {success_count}/{len(device_ids)} device(s)\n\n"
                f"Device Info HW is now open to verify the changes.\n"
                f"Reboot the device(s) to apply changes."
            )
        else:
            self.add_activity(f"❌ MaxChange failed - check root access and APK installation")
            QMessageBox.warning(
                self, "MaxChange Failed",
                "Failed to change device(s).\n\n"
                "Please check:\n"
                "• Device has root access (su)\n"
                "• MaxChange APK is installed\n"
                "• Profile files exist in maxchanger/ folder"
            )
    

    def _maxchange_check_device(self):
        """Check current MaxChange device info for selected devices."""
        rows = self.auto_reg_device_select.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "No Device Selected", "Please select at least one device from the list.")
            return
        device_ids = [self.auto_reg_device_select.item(r.row(), 0).text().split('. ', 1)[-1].strip()
                     for r in rows if self.auto_reg_device_select.item(r.row(), 0)]
        
        if not device_ids:
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


    def start_registration(self):
        # Start elapsed timer
        if hasattr(self, 'ar_time_label'):
            self._ar_elapsed = 0
            self.ar_time_label.setText("Time: 0s")
            if not hasattr(self, '_ar_timer'):
                self._ar_timer = QTimer()
                self._ar_timer.timeout.connect(self._tick_ar_timer)
            self._ar_timer.start(1000)
        apk = self.apk_input.text().strip()
        first_names_list = self.first_name_input.text().strip()
        last_names_list = self.last_name_input.text().strip()
        base_email = self.email_input.text().strip()
        password = self.password_input.text().strip()
        base_birthday = self.birthday_input.text().strip()
        gender = self.gender_input.currentText() or "Male"
        phone = self.phone_input.text().strip()
        
        # Get selected devices
        selected_devices = self.get_selected_devices()
        
        # Grant write permissions to APK file and folder for Appium signing
        if apk and os.path.exists(apk):
            try:
                apk_folder = os.path.dirname(apk)
                # Grant full permissions to APK file
                subprocess.run(['icacls', apk, '/grant', 'Everyone:F', '/T'], 
                             capture_output=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                # Grant full permissions to folder
                subprocess.run(['icacls', apk_folder, '/grant', 'Everyone:F', '/T'], 
                             capture_output=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                self.add_activity("✓ APK permissions granted for Appium signing")
            except Exception as e:
                self.add_activity(f"⚠️ Could not grant APK permissions: {e}")
        
        # Fall back to legacy device input if no checkboxes
        if not selected_devices:
            device = self.device_input.text().strip()
            if device:
                selected_devices = [device]
        
        if not apk:
            QMessageBox.warning(self, "Error", "Please select APK file!")
            return
        if not selected_devices:
            QMessageBox.warning(self, "Error", "No devices selected! Go to Settings and refresh devices.")
            return
        
        # Check if using email or phone
        use_email = self.use_email_checkbox.isChecked()
        use_phone = self.use_phone_checkbox.isChecked()
        
        # Validate based on signup method
        if use_email and not base_email:
            QMessageBox.warning(self, "Error", "Please enter email address!")
            return
        
        if use_phone and not self.random_phone_checkbox.isChecked() and not phone:
            QMessageBox.warning(self, "Error", "Please enter phone number or enable Random Phone!")
            return
        
        # Common required fields
        # Skip password validation if random password is enabled
        if self.random_password_checkbox.isChecked():
            if not all([first_names_list, last_names_list, base_birthday]):
                QMessageBox.warning(self, "Error", "Please fill all required fields (names, birthday)!")
                return
        else:
            if not all([first_names_list, last_names_list, password, base_birthday]):
                QMessageBox.warning(self, "Error", "Please fill all required fields (names, password, birthday)!")
                return
        
        # Generate account data from name combinations
        accounts = self.generate_account_data(
            first_names_list, last_names_list, base_email, password, 
            base_birthday, gender, phone
        )
        
        if not accounts:
            QMessageBox.warning(self, "Error", "No valid name combinations found! Please check your first and last names.")
            return
        
        # Calculate total registrations based on mode
        if len(selected_devices) == 1:
            # Single device: all accounts run sequentially
            total_registrations = len(accounts)
        else:
            # Multiple devices: accounts distributed across devices
            total_registrations = len(accounts)
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.update_status(f"Creating {total_registrations} accounts on {len(selected_devices)} device(s)...")
        
        # Keep UI responsive
        QApplication.processEvents()
        
        # Update dashboard
        self.update_dashboard_status("🟢 Running", "#4CAF50")
        self.device_status_label.setText(f"Devices: {len(selected_devices)}")
        self.add_activity(f"Started creating {total_registrations} accounts total")
        
        # Keep UI responsive
        QApplication.processEvents()
        
        # Store registrations for multi-device
        self.registrations = []
        self.worker_threads = []
        self.log_signals = []  # Keep references to prevent deletion
        self.stop_flag = False  # Flag to stop registration
        
        # Set active threads count
        if len(selected_devices) == 1:
            # Single device sequential mode: 1 thread
            self.active_threads = 1
        else:
            # Multiple devices parallel mode: number of accounts (distributed across devices)
            self.active_threads = len(accounts)
        
        # Get delay settings
        action_delay = self.get_action_delay()
        safety_mode = self.get_safety_mode()
        
        self.add_activity(f"Using action delay: {action_delay}s, Safety mode: {'ON' if safety_mode else 'OFF'}")
        
        # Create registrations for each device and each account
        # IMPORTANT: For single device, run sequentially to avoid conflicts
        # For multiple devices, each device can run in parallel
        
        if len(selected_devices) == 1:
            # Single device: Run accounts sequentially (one after another)
            self.add_activity(f"⚠️ Single device detected - Running accounts sequentially to avoid conflicts")
            
            device = selected_devices[0]
            for account_idx, account in enumerate(accounts):
                device_email = account['email']
                
                log_signal = LogSignal()
                log_signal.log.connect(lambda msg, d=device: self.log(f"[{d[-8:]}] {msg}"))
                log_signal.status.connect(lambda status, e=device_email: self.update_device_status(e, status))
                log_signal.finished.connect(self.on_thread_finished)
                
                # Keep reference to prevent deletion
                self.log_signals.append(log_signal)
                
                # Get app selection
                app_selection = self.app_selection_input.currentText() if hasattr(self, 'app_selection_input') else "Facebook Lite"
                
                from src.automation.registration import FacebookRegistration
                
                registration = FacebookRegistration(apk, device, log_signal, action_delay, safety_mode, app_selection)
                
                # Apply device changer if enabled
                self.apply_device_changer_to_registration(registration)
                
                self.registrations.append(registration)
                
                # Add account to table with all details
                self.add_account_to_table(
                    device_email, 
                    account['password'], 
                    account['first_name'], 
                    account['last_name'], 
                    account['birthday'], 
                    account['gender'], 
                    device, 
                    "⏳ Waiting", 
                    f"Account {account_idx+1}/{len(accounts)}"
                )
                
                # Keep UI responsive during setup
                QApplication.processEvents()
            
            # Start sequential processing in a single thread
            def process_accounts_sequentially():
                for idx, (registration, account) in enumerate(zip(self.registrations, accounts)):
                    if hasattr(self, 'stop_flag') and self.stop_flag:
                        self.add_activity(f"⏹️ Registration stopped by user")
                        break
                    
                    device_email = account['email']
                    # Create display identifier (email or phone)
                    display_id = device_email if device_email else f"Phone: {account.get('phone', 'N/A')}"
                    
                    self.add_activity(f"📝 Processing account {idx+1}/{len(accounts)}: {display_id}")
                    self.update_account_status(device_email if device_email else account.get('phone', ''), "🟢 Running", "Registration in progress")
                    
                    try:
                        registration.register(
                            account['first_name'], 
                            account['last_name'], 
                            device_email, 
                            account['password'], 
                            account['birthday'], 
                            account['gender'],
                            account.get('phone', ''),
                            self.use_phone_checkbox.isChecked()
                        )
                        self.add_activity(f"✅ Completed account {idx+1}/{len(accounts)}: {display_id}")
                    except Exception as e:
                        self.add_activity(f"❌ Failed account {idx+1}/{len(accounts)}: {display_id} - {e}")
                    
                    # Small delay between accounts
                    if idx < len(accounts) - 1:  # Don't delay after last account
                        self.add_activity(f"⏳ Waiting {action_delay}s before next account...")
                        time.sleep(action_delay)
                
                # All done
                self.add_activity(f"🎉 Sequential processing completed!")
                self.on_thread_finished()
            
            thread = threading.Thread(target=process_accounts_sequentially, daemon=True)
            self.worker_threads.append(thread)
            thread.start()
            
        else:
            # Multiple devices: Distribute accounts across devices (one account per device in parallel)
            self.add_activity(f"🚀 Multiple devices detected - Distributing {len(accounts)} accounts across {len(selected_devices)} devices")
            
            # Distribute accounts across devices
            for account_idx, account in enumerate(accounts):
                # Assign to device using round-robin
                device_idx = account_idx % len(selected_devices)
                device = selected_devices[device_idx]
                
                # Generate unique email for device + account combination
                device_email = account['email']
                if len(selected_devices) > 1 and '@' in device_email:
                    # Add device suffix if multiple devices and it's an email
                    email_parts = device_email.split('@')
                    device_email = f"{email_parts[0]}_d{device_idx+1}@{email_parts[1]}"
                elif len(selected_devices) > 1:
                    # For phone numbers, just append device index
                    device_email = f"{device_email}_d{device_idx+1}"
                
                log_signal = LogSignal()
                log_signal.log.connect(lambda msg, d=device: self.log(f"[{d[-8:]}] {msg}"))
                log_signal.status.connect(lambda status, e=device_email: self.update_device_status(e, status))
                log_signal.finished.connect(self.on_thread_finished)
                
                # Keep reference to prevent deletion
                self.log_signals.append(log_signal)
                
                # Get app selection
                app_selection = self.app_selection_input.currentText() if hasattr(self, 'app_selection_input') else "Facebook Lite"
                
                from src.automation.registration import FacebookRegistration
                
                registration = FacebookRegistration(apk, device, log_signal, action_delay, safety_mode, app_selection)
                
                # Apply device changer if enabled
                self.apply_device_changer_to_registration(registration)
                
                self.registrations.append(registration)
                
                # Add account to table with all details
                self.add_account_to_table(
                    device_email, 
                    account['password'], 
                    account['first_name'], 
                    account['last_name'], 
                    account['birthday'], 
                    account['gender'], 
                    device, 
                    "⏳ Waiting", 
                    f"Account {account_idx+1}/{len(accounts)}"
                )
                
                thread = threading.Thread(
                    target=registration.register,
                    args=(account['first_name'], account['last_name'], device_email, 
                          account['password'], account['birthday'], account['gender'])
                )
                self.worker_threads.append(thread)
                thread.start()
                
                self.add_activity(f"Started {device_email} on device {device[-8:]}")
                
                # Keep UI responsive during setup
                QApplication.processEvents()
    

    def update_device_status(self, email, status):
        """Update status for a specific device/email in the table."""
        # Update the table with more descriptive statuses
        if "Running" in status:
            self.update_account_status(email, "🟢 Running", "Registration in progress")
        elif "Error" in status or "Stopped" in status:
            self.update_account_status(email, "❌ Failed", "Registration failed")
            # Update failed count
            self.total_accounts += 1
            self.issues_count += 1
            self.update_statistics_display()
            self.add_activity(f"Registration failed for {email}")
        elif "Completed" in status:
            self.update_account_status(email, "✅ Success", "Account created successfully")
            # Update success count
            self.total_accounts += 1
            self.working_count += 1
            self.today_count += 1
            self.update_statistics_display()
            self.add_activity(f"Account created: {email}")
        elif "Connecting" in status:
            self.update_account_status(email, "🔄 Connecting", "Connecting to device")
        elif "Loading" in status:
            self.update_account_status(email, "🔄 Loading", "Loading Facebook Lite")
        elif "Starting" in status:
            self.update_account_status(email, "🟡 Starting", "Initializing registration")
        elif "Entering" in status:
            self.update_account_status(email, "📝 Entering", "Entering account details")
        elif "Submitting" in status:
            self.update_account_status(email, "📤 Submitting", "Submitting registration")
        
        # Also update the main status label
        self.update_status(status)

    def update_device_changer_status(self, checked):
        """Update UI when device changer checkbox is toggled."""
        if checked:
            self.add_activity("✓ Device spoofing enabled")
        else:
            self.add_activity("✗ Device spoofing disabled")
    

    def on_thread_finished(self):
        """Called when a single device thread finishes."""
        self.active_threads -= 1
        if self.active_threads <= 0:
            self.on_finished()
            # Clean up references
            self.log_signals.clear()
            self.registrations.clear()
            self.worker_threads.clear()
        

    def _tick_ar_timer(self):
        if not hasattr(self, '_ar_elapsed'):
            self._ar_elapsed = 0
        self._ar_elapsed += 1
        if hasattr(self, 'ar_time_label'):
            m, s = divmod(self._ar_elapsed, 60)
            self.ar_time_label.setText(f"Time: {m}m {s}s" if m else f"Time: {s}s")


    def stop_registration(self):
        # Stop elapsed timer
        if hasattr(self, '_ar_timer'):
            self._ar_timer.stop()
        # Set stop flag for sequential processing
        self.stop_flag = True
        
        if hasattr(self, 'registrations') and self.registrations:
            self.log("[!] Stopping all devices...")
            for reg in self.registrations:
                reg.stop()
            self.update_status("Stopped")
            self.update_dashboard_status("🔴 Stopped", "#f44336")
            self.add_activity("Registration stopped by user")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            # Clean up references
            if hasattr(self, 'log_signals'):
                self.log_signals.clear()
            self.registrations.clear()
            if hasattr(self, 'worker_threads'):
                self.worker_threads.clear()
        elif self.registration:
            self.log("[!] Stopping...")
            self.registration.stop()
            self.update_status("Stopped")
            self.update_dashboard_status("🔴 Stopped", "#f44336")
            self.add_activity("Registration stopped by user")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)

    # Use a code/monospace font for the whole app
    # Priority: Consolas (Windows) → JetBrains Mono → Cascadia Code → Courier New (fallback)
    _code_font = QFont()
    _code_font.setFamilies(["Consolas", "JetBrains Mono", "Cascadia Code", "Fira Code", "Courier New", "Monospace"])
    _code_font.setPointSize(10)
    app.setFont(_code_font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

    def log(self, msg):
        # Add to activity log on dashboard instead of removed log output
        self.add_activity(msg)
        

    def update_status(self, status):
        if "Running" in status:
            self.update_dashboard_status("🟢 Running", "#4CAF50")
        elif "Error" in status or "Stopped" in status:
            self.update_dashboard_status("🔴 " + status, "#f44336")
            # Update failed count
            self.total_accounts += 1
            self.issues_count += 1
            self.update_statistics_display()
            self.add_activity(f"Registration failed - Issue detected")
        elif "Completed" in status:
            self.update_dashboard_status("✅ Completed", "#4CAF50")
            # Update success count
            self.total_accounts += 1
            self.working_count += 1
            self.today_count += 1
            self.update_statistics_display()
            self.add_activity(f"Account created successfully")
        

    def on_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.update_dashboard_status("⚪ Idle", "#888888")
        
