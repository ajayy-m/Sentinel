from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QApplication

from sentinel.ui.main_window import SentinelMainWindow


APP_STYLESHEET = """
/* Classic Windows-style UI (flat, grays, no rounded corners) */
QWidget {
    background: #c0c0c0;
    color: #000000;
    font-family: Tahoma, "MS Sans Serif", Arial;
    font-size: 10px;
}
QMainWindow {
    background: #c0c0c0;
}
QLabel#sentinelHeader {
    color: #000000;
    font-size: 14px;
    font-weight: 700;
}
QLabel#sentinelSubtitle {
    color: #000000;
    font-size: 10px;
}
QGroupBox {
    color: #000000;
    border: 2px solid #808080;
    margin-top: 10px;
    padding: 6px;
    font-weight: 600;
    background: #cfcfcf;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QLabel#metricValue {
    color: #000000;
    font-size: 11px;
    font-weight: 600;
}
QPlainTextEdit, QTextEdit, QLineEdit {
    background-color: #ffffff;
    color: #000000;
    border: 1px solid #808080;
}
QTabWidget::pane {
    border: 2px solid #808080;
    background: #cfcfcf;
}
QTabBar::tab {
    background: #c0c0c0;
    color: #000000;
    font-size: 11px;
    padding: 6px 10px;
    min-height: 22px;
    margin-right: 0px;
    border: 1px solid #808080;
}
QTabBar::tab:selected {
    background: #e0e0e0;
    border-bottom: 2px solid #c0c0c0;
}
QTableWidget {
    background: #ffffff;
    color: #000000;
    font-size: 11px;
    alternate-background-color: #f0f0f0;
    gridline-color: #808080;
    selection-background-color: #000080;
    selection-color: #ffffff;
    border: 1px solid #808080;
}
QHeaderView::section {
    background-color: #dcdcdc;
    color: #000000;
    font-size: 11px;
    padding: 6px;
    border: 1px solid #808080;
}
QProgressBar {
    border: 1px solid #808080;
    background: #ffffff;
}
QProgressBar::chunk {
    background-color: #000080;
}
QPushButton {
    background: #dcdcdc;
    border: 2px outset #808080;
    padding: 4px 8px;
}
QPushButton:pressed {
    border: 2px inset #808080;
}
/* Reduce visual padding and use smaller header to mimic legacy tools */
QLabel#sentinelHeader {
    font-size: 11px;
    font-weight: 600;
}
QLabel#sentinelSubtitle {
    font-size: 9px;
}
QGroupBox {
    padding: 4px;
    margin-top: 8px;
}
QTabBar::tab {
    border-radius: 0px;
}
"""


def run_ui(config: dict[str, Any]) -> None:
    app = QApplication([])
    # Prefer the native Windows-style, then apply a classic palette-like stylesheet
    try:
        app.setStyle("Windows")
    except Exception:
        pass
    app.setStyleSheet(APP_STYLESHEET)
    window = SentinelMainWindow(config)
    window.show()
    app.exec()
