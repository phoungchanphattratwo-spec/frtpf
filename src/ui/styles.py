"""
Application-wide dark stylesheet.

Import and apply once at startup:
    from src.ui.styles import DARK_STYLE
    app.setStyleSheet(DARK_STYLE)
"""

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1a1a1a;
    color: #e0e0e0;
    font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', 'Fira Code', 'Courier New', monospace;
    font-size: 13px;
}
QScrollBar:horizontal, QScrollBar:vertical {
    background: transparent;
    width: 0px;
    height: 0px;
    border: none;
}
QScrollBar::handle:horizontal, QScrollBar::handle:vertical {
    background: transparent;
    border: none;
}
QScrollBar::add-line:horizontal, QScrollBar::add-line:vertical,
QScrollBar::sub-line:horizontal, QScrollBar::sub-line:vertical {
    background: transparent;
    border: none;
    width: 0px;
    height: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::add-page:vertical,
QScrollBar::sub-page:horizontal, QScrollBar::sub-page:vertical {
    background: transparent;
}
QGroupBox {
    border: 1px solid #2d2d2d;
    border-radius: 0px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
    color: #00bcd4;
    font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', 'Courier New', monospace;
    background-color: #242424;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 15px;
    padding: 0 8px;
}
QLineEdit {
    background-color: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 0px;
    padding: 10px 12px;
    color: #e0e0e0;
    font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', 'Courier New', monospace;
    font-size: 13px;
}
QLineEdit:focus {
    border: 1px solid #00bcd4;
    background-color: #2d2d2d;
}
QLineEdit:disabled {
    background-color: #222222;
    color: #666666;
}
QTextEdit {
    background-color: #1a1a1a;
    border: 1px solid #2d2d2d;
    border-radius: 0px;
    color: #00ff00;
    font-family: 'Consolas', 'Courier New', monospace;
    padding: 8px;
}
QPushButton {
    border-radius: 0px;
    padding: 12px 24px;
    font-weight: 600;
    font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', 'Courier New', monospace;
    font-size: 13px;
    border: none;
}
QPushButton:disabled {
    background-color: #333333;
    color: #666666;
}
QLabel {
    color: #b0b0b0;
    font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', 'Courier New', monospace;
}
QTabBar::tab {
    font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', 'Courier New', monospace;
    font-size: 13px;
    font-weight: 500;
}
QAbstractItemView::item:selected {
    background-color: rgba(76, 175, 80, 0.15);
    color: #4CAF50;
}
QAbstractItemView::item:hover {
    background-color: #3d3d3d;
}
"""
