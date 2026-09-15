"""Qt stylesheet and visual tokens."""

from __future__ import annotations

DARK = {
    "bg": "#090e14",
    "bg_alt": "#0d131b",
    "sidebar": "#0c131b",
    "topbar": "#0d141d",
    "card": "#121b25",
    "card_alt": "#17222e",
    "border": "#263444",
    "text": "#f2f6fb",
    "muted": "#8d9caf",
    "faint": "#627085",
    "accent": "#43d6a3",
    "accent_hover": "#57e7b5",
    "blue": "#55a9ff",
    "danger": "#ff6273",
    "warning": "#f6ba58",
}
LIGHT = {
    "bg": "#f1f5f9",
    "bg_alt": "#e7eef5",
    "sidebar": "#ffffff",
    "topbar": "#ffffff",
    "card": "#ffffff",
    "card_alt": "#f7fafc",
    "border": "#d8e2ec",
    "text": "#172231",
    "muted": "#66768a",
    "faint": "#93a0b0",
    "accent": "#0f9f72",
    "accent_hover": "#087f5b",
    "blue": "#2378d6",
    "danger": "#d93f52",
    "warning": "#b76d00",
}


def build_stylesheet(theme: str = "dark") -> str:
    c = LIGHT if theme == "light" else DARK
    return f"""
    * {{ font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif; outline: none; }}
    QMainWindow, QWidget#AppRoot {{ background: {c["bg"]}; color: {c["text"]}; }}
    QWidget {{ color: {c["text"]}; font-size: 13px; }}
    QFrame#Sidebar {{ background: {c["sidebar"]}; border-right: 1px solid {c["border"]}; }}
    QFrame#TopBar {{ background: {c["topbar"]}; border-bottom: 1px solid {c["border"]}; }}
    QFrame[card="true"] {{ background: {c["card"]}; border: 1px solid {c["border"]}; border-radius: 16px; }}
    QFrame[card="soft"] {{ background: {c["card_alt"]}; border: 1px solid {c["border"]}; border-radius: 12px; }}
    QLabel[role="brand"] {{ color: {c["text"]}; font-size: 24px; font-weight: 700; }}
    QLabel[role="brandSub"] {{ color: {c["muted"]}; font-size: 11px; letter-spacing: 1px; }}
    QLabel[role="title"] {{ font-size: 20px; font-weight: 700; color: {c["text"]}; }}
    QLabel[role="section"] {{ font-size: 15px; font-weight: 650; color: {c["text"]}; }}
    QLabel[role="muted"] {{ color: {c["muted"]}; }}
    QLabel[role="metric"] {{ font-size: 30px; font-weight: 750; color: {c["text"]}; }}
    QLabel[role="accent"] {{ color: {c["accent"]}; font-weight: 650; }}
    QLabel[role="danger"] {{ color: {c["danger"]}; font-weight: 650; }}
    QLabel[role="warning"] {{ color: {c["warning"]}; font-weight: 650; }}
    QPushButton {{
        min-height: 36px; padding: 0 15px; border-radius: 10px;
        border: 1px solid {c["border"]}; background: {c["card_alt"]};
        color: {c["text"]}; font-weight: 600;
    }}
    QPushButton:hover {{ border-color: {c["faint"]}; background: {c["border"]}; }}
    QPushButton:pressed {{ padding-top: 1px; }}
    QPushButton:disabled {{ color: {c["faint"]}; background: {c["card_alt"]}; border-color: {c["border"]}; }}
    QPushButton[variant="primary"] {{ background: {c["accent"]}; border-color: {c["accent"]}; color: #06150f; }}
    QPushButton[variant="primary"]:hover {{ background: {c["accent_hover"]}; border-color: {c["accent_hover"]}; }}
    QPushButton[variant="blue"] {{ background: {c["blue"]}; border-color: {c["blue"]}; color: #ffffff; }}
    QPushButton[variant="danger"] {{ background: transparent; color: {c["danger"]}; border-color: {c["danger"]}; }}
    QPushButton[variant="danger"]:hover {{ background: {c["danger"]}; color: #ffffff; }}
    QPushButton[variant="ghost"] {{ background: transparent; border-color: transparent; color: {c["muted"]}; text-align: left; padding-left: 16px; }}
    QPushButton[variant="ghost"]:hover {{ background: {c["card_alt"]}; color: {c["text"]}; }}
    QPushButton[nav="true"] {{
        background: transparent; border: none; border-radius: 11px; min-height: 43px;
        padding: 0 14px; text-align: left; color: {c["muted"]}; font-weight: 600;
    }}
    QPushButton[nav="true"]:hover {{ background: {c["card_alt"]}; color: {c["text"]}; }}
    QPushButton[nav="true"]:checked {{
        background: {c["accent"]}22; color: {c["accent"]};
        border-left: 3px solid {c["accent"]}; padding-left: 11px;
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        min-height: 38px; padding: 0 11px; border: 1px solid {c["border"]};
        border-radius: 10px; background: {c["bg_alt"]}; color: {c["text"]};
        selection-background-color: {c["accent"]}; selection-color: #07130f;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {c["accent"]}; }}
    QComboBox::drop-down {{ width: 28px; border: none; }}
    QComboBox QAbstractItemView {{ background: {c["card"]}; color: {c["text"]}; border: 1px solid {c["border"]}; selection-background-color: {c["border"]}; padding: 4px; }}
    QCheckBox {{ spacing: 9px; color: {c["text"]}; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {c["border"]}; background: {c["bg_alt"]}; }}
    QCheckBox::indicator:checked {{ background: {c["accent"]}; border-color: {c["accent"]}; }}
    QTableWidget, QTreeWidget, QListWidget {{ background: transparent; alternate-background-color: {c["card_alt"]}; border: none; gridline-color: {c["border"]}; selection-background-color: {c["border"]}; selection-color: {c["text"]}; }}
    QHeaderView::section {{ background: {c["bg_alt"]}; color: {c["muted"]}; border: none; border-bottom: 1px solid {c["border"]}; padding: 10px 8px; font-weight: 650; }}
    QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {c["border"]}66; }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ width: 8px; background: transparent; margin: 3px; }}
    QScrollBar::handle:vertical {{ background: {c["border"]}; min-height: 30px; border-radius: 4px; }}
    QScrollBar::handle:vertical:hover {{ background: {c["faint"]}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ height: 0; background: transparent; }}
    QToolTip {{ background: {c["card"]}; color: {c["text"]}; border: 1px solid {c["border"]}; padding: 5px; border-radius: 6px; }}
    QProgressBar {{ height: 8px; border: none; border-radius: 4px; background: {c["border"]}; text-align: center; }}
    QProgressBar::chunk {{ border-radius: 4px; background: {c["accent"]}; }}
    QSplitter::handle {{ background: transparent; width: 8px; }}
    QDialog {{ background: {c["bg"]}; color: {c["text"]}; }}
    """
