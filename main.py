"""
FRT — Facebook Register Tool
Entry point.
"""

import sys
import threading
import time

# ── Windows: suppress console window for all subprocess calls ────────────────
from src.core.subprocess_utils import patch_subprocess
patch_subprocess()

# ── Qt application ────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import (
    QApplication, QDialog, QMessageBox, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal

from src.ui.styles import DARK_STYLE
from src.ui.main_window import MainWindow
from src.core.license_config import SUPABASE_URL, SUPABASE_KEY


class LicenseWatchdog(QObject):
    """Emits signal on main thread when license is invalid."""
    license_invalid = pyqtSignal(str)

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self._running = True

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            time.sleep(20)
            if not self._running:
                break
            try:
                is_valid, message = self.manager.check_license_status()
                if not is_valid:
                    self.license_invalid.emit(message)
                    break
            except Exception:
                pass


def _is_access_denied_message(message: str) -> bool:
    """Return True when the failure is a ban or admin-disable — not fixable by entering a key."""
    msg_lower = message.lower()
    return (
        'banned' in msg_lower
        or 'deactivated' in msg_lower
        or 'disabled' in msg_lower
        or 'deactivated by administrator' in msg_lower
    )


def _denied_state_file() -> str:
    import os
    return os.path.join(os.path.expanduser('~'), '.frt_denied.json')


def _save_denied_state(message: str) -> None:
    """Persist the ban/disable reason so next startup shows the card, not the key dialog."""
    import os, json
    try:
        with open(_denied_state_file(), 'w', encoding='utf-8') as f:
            json.dump({'message': message}, f)
    except Exception:
        pass


def _load_denied_state() -> str:
    """Return the saved denial message, or empty string if none."""
    import os, json
    try:
        path = _denied_state_file()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f).get('message', '')
    except Exception:
        pass
    return ''


def _clear_denied_state() -> None:
    import os
    try:
        path = _denied_state_file()
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def show_access_denied_screen(window: MainWindow, message: str) -> None:
    """Show a clean centered card over the window for ban/disable — no activation dialog."""
    import qtawesome as qta

    is_banned = 'banned' in message.lower()

    # ── Dark full-window backdrop ─────────────────────────────────────────
    overlay = QWidget(window)
    overlay.setStyleSheet("background: rgba(0,0,0,0.82);")
    overlay.setGeometry(window.rect())
    overlay.show()
    overlay.raise_()

    # ── Center layout ─────────────────────────────────────────────────────
    outer = QVBoxLayout(overlay)
    outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
    outer.setContentsMargins(0, 0, 0, 0)

    # ── Card ──────────────────────────────────────────────────────────────
    card = QWidget()
    card.setFixedWidth(480)
    card.setStyleSheet("""
        QWidget {
            background: #16161f;
            border-radius: 20px;
            border: 1px solid rgba(239,68,68,0.25);
        }
    """)

    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(36, 36, 36, 28)
    card_layout.setSpacing(0)
    card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # Icon
    icon_lbl = QLabel()
    pix = qta.icon('fa5s.ban' if is_banned else 'fa5s.lock', color='#ef4444').pixmap(52, 52)
    icon_lbl.setPixmap(pix)
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_lbl.setStyleSheet("background: transparent; border: none;")
    card_layout.addWidget(icon_lbl)

    card_layout.addSpacing(16)

    # Title
    title = QLabel("Account Banned" if is_banned else "License Disabled")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(
        "color: #ef4444; font-size: 20px; font-weight: 700; "
        "background: transparent; border: none;"
    )
    card_layout.addWidget(title)

    card_layout.addSpacing(8)

    # Subtitle / reason
    # Strip the "Your account has been banned.\nReason:" prefix for cleaner display
    display_msg = message
    if '\nReason:' in message:
        display_msg = message.split('\nReason:')[-1].strip()
    elif 'deactivated by administrator' in message.lower():
        display_msg = "Your license has been disabled by the administrator."

    sub = QLabel(display_msg)
    sub.setWordWrap(True)
    sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
    sub.setStyleSheet(
        "color: rgba(255,255,255,0.45); font-size: 13px; "
        "background: transparent; border: none;"
    )
    card_layout.addWidget(sub)

    card_layout.addSpacing(24)

    # Divider
    div = QWidget()
    div.setFixedHeight(1)
    div.setStyleSheet("background: rgba(255,255,255,0.07); border: none;")
    card_layout.addWidget(div)

    card_layout.addSpacing(20)

    # Features list — vertical, clean
    features_lbl = QLabel("What you get with an active license")
    features_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    features_lbl.setStyleSheet(
        "color: rgba(255,255,255,0.3); font-size: 10px; letter-spacing: 1px; "
        "background: transparent; border: none;"
    )
    card_layout.addWidget(features_lbl)

    card_layout.addSpacing(12)

    features = [
        ("fa5s.robot",          "#4d9fff", "Automated Facebook Registration"),
        ("fa5s.mobile-alt",     "#22c55e", "Multi-Device Management & ADB Control"),
        ("fa5s.user-shield",    "#a855f7", "Account Backup, Restore & Seeding"),
        ("fa5s.chart-bar",      "#f97316", "Real-time Dashboard & Analytics"),
    ]

    for icon_name, color, text in features:
        row = QHBoxLayout()
        row.setSpacing(10)
        row.setContentsMargins(8, 0, 8, 0)

        ic = QLabel()
        ic.setPixmap(qta.icon(icon_name, color=color).pixmap(13, 13))
        ic.setFixedWidth(18)
        ic.setStyleSheet("background: transparent; border: none;")
        row.addWidget(ic)

        tl = QLabel(text)
        tl.setStyleSheet(
            "color: rgba(255,255,255,0.5); font-size: 12px; "
            "background: transparent; border: none;"
        )
        row.addWidget(tl)
        row.addStretch()
        card_layout.addLayout(row)
        card_layout.addSpacing(6)

    card_layout.addSpacing(20)

    # Buttons
    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)

    contact_btn = QPushButton("Contact Support")
    contact_btn.setIcon(qta.icon('fa5b.telegram', color='white'))
    contact_btn.setFixedHeight(42)
    contact_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    contact_btn.setStyleSheet("""
        QPushButton {
            background: #2563eb;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 600;
            padding: 0 20px;
        }
        QPushButton:hover { background: #3b82f6; }
        QPushButton:pressed { background: #1d4ed8; }
    """)

    def _open_telegram():
        import webbrowser
        webbrowser.open("https://t.me/ftoolpro")

    contact_btn.clicked.connect(_open_telegram)
    btn_row.addWidget(contact_btn)

    close_btn = QPushButton("Close")
    close_btn.setFixedHeight(42)
    close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    close_btn.setStyleSheet("""
        QPushButton {
            background: rgba(255,255,255,0.07);
            color: rgba(255,255,255,0.55);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            font-size: 13px;
            font-weight: 600;
            padding: 0 20px;
        }
        QPushButton:hover { background: rgba(255,255,255,0.12); color: white; }
    """)
    close_btn.clicked.connect(window.close)
    btn_row.addWidget(close_btn)

    card_layout.addLayout(btn_row)

    outer.addWidget(card)

    # Keep overlay covering the window on resize
    _orig_resize = window.resizeEvent
    def _on_resize(e, ov=overlay):
        ov.setGeometry(window.rect())
        _orig_resize(e)
    window.resizeEvent = _on_resize


def check_license(app: QApplication, window: MainWindow):
    """Check license validity on the MAIN THREAD (required for dialog).
    Returns (is_valid, manager, access_denied).
    access_denied=True means a ban/disable screen is showing — keep the event loop.
    """
    from src.core.license_manager import LicenseManager
    from src.ui.license_dialog import LicenseActivationDialog

    manager = LicenseManager(SUPABASE_URL, SUPABASE_KEY)

    # ── Normal startup validation (license_manager handles denied state internally) ───
    is_valid, message, license_data = manager.validate_license()

    if is_valid:
        return True, manager, False

    # ── Banned or admin-disabled: show card ─────────────────
    if _is_access_denied_message(message):
        show_access_denied_screen(window, message)
        return False, manager, True

    # ── Normal invalid license: show activation dialog ────────────────────
    overlay = QWidget(window)
    overlay.setStyleSheet("background: rgba(0, 0, 0, 0.65);")
    overlay.setGeometry(window.rect())
    overlay.show()
    overlay.raise_()

    dialog = LicenseActivationDialog(manager, window)
    geo = window.geometry()
    dx = geo.x() + (geo.width() - dialog.width()) // 2
    dy = geo.y() + (geo.height() - dialog.height()) // 2
    dialog.move(dx, dy)
    dialog.raise_()

    result = dialog.exec()

    overlay.hide()
    overlay.deleteLater()

    if result == QDialog.DialogCode.Accepted:
        return True, manager, False

    # User closed the dialog - just exit silently without showing another dialog
    return False, manager, False


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)

    font = QFont()
    font.setFamilies(["Consolas", "JetBrains Mono", "Cascadia Code", "Fira Code", "Courier New", "Monospace"])
    font.setPointSize(10)
    app.setFont(font)

    # Show main window FIRST — user sees the UI immediately
    window = MainWindow()
    window.show()

    # Let Qt paint the window before doing any blocking work
    QApplication.processEvents()

    # License check runs after window is visible (still on main thread for dialog support)
    licensed, manager, access_denied = check_license(app, window)
    if not licensed:
        if access_denied:
            # Access-denied screen is showing — keep the event loop so the
            # user can read it and click Close / Contact Support.
            sys.exit(app.exec())
        else:
            sys.exit(0)

    # Start watchdog - checks every 20 seconds in background
    watchdog = LicenseWatchdog(manager)

    def on_license_invalid(message: str):
        watchdog.stop()

        # Banned or admin-disabled: show the card
        if _is_access_denied_message(message):
            show_access_denied_screen(window, message)
        else:
            QMessageBox.critical(
                window,
                "License Deactivated",
                f"Your license has been deactivated.\n\nReason: {message}\n\n"
                "Please contact t.me/ftoolpro for support."
            )
            window.close()
            app.quit()

    watchdog.license_invalid.connect(on_license_invalid)
    watchdog.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
