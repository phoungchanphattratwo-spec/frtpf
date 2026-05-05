"""
License Activation Dialog - Modern Redesign
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QApplication, QWidget
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath
import qtawesome as qta


class LicenseActivationWorker(QThread):
    finished = pyqtSignal(bool, str, object)

    def __init__(self, license_manager, license_key):
        super().__init__()
        self.license_manager = license_manager
        self.license_key = license_key

    def run(self):
        success, message, data = self.license_manager.activate_license(self.license_key)
        self.finished.emit(success, message, data)


class LicenseActivationDialog(QDialog):
    license_activated = pyqtSignal(dict)

    def __init__(self, license_manager, parent=None):
        super().__init__(parent)
        self.license_manager = license_manager
        self.worker = None

        self.setWindowTitle("Activate License")
        self.setFixedSize(480, 380)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._build_ui()

    def _build_ui(self):
        # Outer layout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Main card
        card = QFrame()
        card.setObjectName("licenseCard")
        card.setStyleSheet("""
            QFrame#licenseCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e1e2e, stop:1 #16161f);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 16, 0)

        # Icon + title
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon('fa5s.shield-alt', color='#FFB300').pixmap(22, 22))
        header_layout.addWidget(icon_lbl)

        header_layout.addSpacing(10)

        title = QLabel("Activate License")
        title.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 700; background: transparent;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Close button
        close_btn = QPushButton()
        close_btn.setIcon(qta.icon('fa5s.times', color='#666666'))
        close_btn.setIconSize(QSize(13, 13))
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.05);
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover { 
                background: #e81123;
            }
        """)
        
        # Store original icon colors
        close_btn._normal_icon = qta.icon('fa5s.times', color='#666666')
        close_btn._hover_icon = qta.icon('fa5s.times', color='#ffffff')
        
        # Override enter/leave events
        def on_enter(event):
            close_btn.setIcon(close_btn._hover_icon)
            QPushButton.enterEvent(close_btn, event)
        
        def on_leave(event):
            close_btn.setIcon(close_btn._normal_icon)
            QPushButton.leaveEvent(close_btn, event)
        
        close_btn.enterEvent = on_enter
        close_btn.leaveEvent = on_leave
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)

        card_layout.addWidget(header)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: rgba(255,255,255,0.06);")
        card_layout.addWidget(div)

        # ── Body ─────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(28, 28, 28, 20)
        body_layout.setSpacing(16)

        # Lock icon centered
        lock_row = QHBoxLayout()
        lock_row.addStretch()
        lock_icon = QLabel()
        lock_icon.setPixmap(qta.icon('fa5s.key', color='#FFB300').pixmap(40, 40))
        lock_row.addWidget(lock_icon)
        lock_row.addStretch()
        body_layout.addLayout(lock_row)

        # Subtitle
        subtitle = QLabel("Enter your license key to unlock\nFacebook Register Tool")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("""
            color: rgba(255,255,255,0.5);
            font-size: 13px;
            line-height: 1.5;
            background: transparent;
        """)
        body_layout.addWidget(subtitle)

        body_layout.addSpacing(4)

        # License key input
        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.license_input.setFixedHeight(52)
        self.license_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Set placeholder text color using palette
        from PyQt6.QtGui import QPalette
        palette = self.license_input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(255, 255, 255, 60))  # Dimmed white
        self.license_input.setPalette(palette)
        
        self.license_input.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.05);
                border: 1.5px solid rgba(255,255,255,0.1);
                border-radius: 12px;
                padding: 0 20px;
                color: #ffffff;
                font-size: 16px;
                font-weight: 700;
                letter-spacing: 3px;
                font-family: 'Consolas', monospace;
            }
            QLineEdit:focus {
                border: 1.5px solid #FFB300;
                background: rgba(255,179,0,0.06);
            }
        """)
        self.license_input.returnPressed.connect(self._activate)
        body_layout.addWidget(self.license_input)

        body_layout.addSpacing(8)

        # Machine ID row
        machine_row = QHBoxLayout()
        machine_row.setContentsMargins(4, 0, 4, 0)

        m_icon = QLabel()
        m_icon.setPixmap(qta.icon('fa5s.desktop', color='#444466').pixmap(13, 13))
        machine_row.addWidget(m_icon)
        machine_row.addSpacing(6)

        mid = self.license_manager.get_machine_id()
        m_label = QLabel(f"Machine ID: {mid}")
        m_label.setStyleSheet("color: rgba(255,255,255,0.25); font-size: 10px; font-family: Consolas; background: transparent;")
        machine_row.addWidget(m_label)
        machine_row.addStretch()

        body_layout.addLayout(machine_row)

        card_layout.addWidget(body)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet("""
            background: rgba(255,255,255,0.03);
            border-bottom-left-radius: 20px;
            border-bottom-right-radius: 20px;
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)
        footer_layout.setSpacing(12)

        # Contact link
        contact = QLabel('<a href="https://t.me/ftoolpro" style="color:#4d9fff;text-decoration:none;">Need a key? Contact us</a>')
        contact.setOpenExternalLinks(True)
        contact.setStyleSheet("font-size: 12px; background: transparent;")
        footer_layout.addWidget(contact)
        footer_layout.addStretch()

        # Activate button
        self.activate_btn = QPushButton("  Activate")
        self.activate_btn.setIcon(qta.icon('fa5s.unlock-alt', color='#1a1a1a'))
        self.activate_btn.setIconSize(QSize(15, 15))
        self.activate_btn.setFixedHeight(44)
        self.activate_btn.setFixedWidth(140)
        self.activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FFB300, stop:1 #FF8F00);
                color: #1a1a1a;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FFC107, stop:1 #FFA000);
            }
            QPushButton:pressed { background: #FF8F00; }
            QPushButton:disabled {
                background: rgba(255,179,0,0.25);
                color: rgba(255,255,255,0.3);
            }
        """)
        self.activate_btn.clicked.connect(self._activate)
        footer_layout.addWidget(self.activate_btn)

        card_layout.addWidget(footer)
        outer.addWidget(card)

    def _activate(self):
        key = self.license_input.text().strip().upper()
        if not key:
            self.license_input.setStyleSheet(self.license_input.styleSheet().replace(
                'border: 1.5px solid rgba(255,255,255,0.1)',
                'border: 1.5px solid #ef4444'
            ))
            return

        self.activate_btn.setEnabled(False)
        self.activate_btn.setText("  Activating...")

        self.worker = LicenseActivationWorker(self.license_manager, key)
        self.worker.finished.connect(self._on_done)
        self.worker.start()

    def _on_done(self, success, message, license_data):
        self.activate_btn.setEnabled(True)
        self.activate_btn.setText("  Activate")

        if success:
            QMessageBox.information(self, "Success", "✓ License activated successfully!")
            self.license_activated.emit(license_data)
            self.accept()
        else:
            QMessageBox.critical(self, "Activation Failed", message)
