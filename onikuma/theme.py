"""
Onikuma CW935 Modern Dark Theme & Stylesheet
===========================================
Obsidian & Electric Cyan/Blue design tokens and Qt StyleSheet (QSS).
"""

# Core Palette
BG_WINDOW = "#0B0D14"
BG_SIDEBAR = "#0F121C"
BG_CARD = "#141826"
BG_CARD_ELEVATED = "#1A2033"
BG_INPUT = "#0E111B"

BORDER_SUBTLE = "#23293D"
BORDER_ACCENT = "#2E6BFF"

ACCENT_PRIMARY = "#2E6BFF"
ACCENT_HOVER = "#477EFF"
ACCENT_GLOW = "#00D2FF"

TEXT_MAIN = "#F3F6FC"
TEXT_SECONDARY = "#9CA6C2"
TEXT_MUTED = "#646E8A"

SUCCESS = "#10B981"
WARNING = "#F59E0B"
ERROR = "#EF4444"

# DPI stage colors matching Onikuma CW935 hardware LEDs
DPI_STAGE_COLORS = [
    ("Blue", "#3B82F6"),
    ("Green", "#10B981"),
    ("Yellow", "#FACC15"),
    ("Cyan", "#06B6D4"),
    ("Magenta", "#EC4899"),
    ("White", "#F8FAFC"),
]


def build_stylesheet() -> str:
    """Return the global Qt StyleSheet for the Onikuma CW935 control panel."""
    return f"""
    QMainWindow, QWidget#CentralRoot {{
        background-color: {BG_WINDOW};
        color: {TEXT_MAIN};
        font-family: "Segoe UI", "Inter", sans-serif;
        font-size: 13px;
    }}

    /* Sidebar Navigation */
    QFrame#Sidebar {{
        background-color: {BG_SIDEBAR};
        border-right: 1px solid {BORDER_SUBTLE};
    }}

    QPushButton[navButton="true"] {{
        background-color: transparent;
        color: {TEXT_SECONDARY};
        border: none;
        border-radius: 10px;
        padding: 11px 14px;
        text-align: left;
        font-size: 13px;
        font-weight: 600;
    }}

    QPushButton[navButton="true"]:hover {{
        background-color: {BG_CARD_ELEVATED};
        color: {TEXT_MAIN};
    }}

    QPushButton[navButton="true"]:checked {{
        background-color: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(46, 107, 255, 0.24),
            stop:1 rgba(0, 210, 255, 0.08)
        );
        color: {TEXT_MAIN};
        border-left: 3px solid {ACCENT_GLOW};
    }}

    /* Top Header Bar */
    QFrame#HeaderBar {{
        background-color: {BG_SIDEBAR};
        border-bottom: 1px solid {BORDER_SUBTLE};
    }}

    /* Cards */
    QFrame[card="true"] {{
        background-color: transparent;
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 14px;
    }}

    QFrame[subCard="true"] {{
        background-color: transparent;
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 10px;
    }}

    QFrame[subCard="true"][activeStage="true"] {{
        background-color: rgba(46, 107, 255, 0.08);
        border: 1px solid {ACCENT_PRIMARY};
    }}

    /* Typography */
    QLabel[heading="page"] {{
        color: {TEXT_MAIN};
        font-size: 20px;
        font-weight: 700;
    }}

    QLabel[heading="section"] {{
        color: {TEXT_MAIN};
        font-size: 15px;
        font-weight: 700;
    }}

    QLabel[muted="true"] {{
        color: {TEXT_SECONDARY};
        font-size: 12px;
    }}

    QLabel[pill="true"] {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 8px;
        padding: 4px 10px;
        color: {TEXT_MAIN};
        font-weight: 600;
        font-size: 12px;
    }}

    /* Primary & Secondary Buttons */
    QPushButton[btnStyle="primary"] {{
        background-color: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {ACCENT_PRIMARY},
            stop:1 #1D4ED8
        );
        color: #FFFFFF;
        border: none;
        border-radius: 9px;
        padding: 9px 18px;
        font-weight: 700;
        font-size: 13px;
    }}

    QPushButton[btnStyle="primary"]:hover {{
        background-color: {ACCENT_HOVER};
    }}

    QPushButton[btnStyle="primary"]:pressed {{
        background-color: #1E40AF;
    }}

    QPushButton[btnStyle="secondary"] {{
        background-color: {BG_CARD_ELEVATED};
        color: {TEXT_MAIN};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 9px;
        padding: 9px 16px;
        font-weight: 600;
        font-size: 13px;
    }}

    QPushButton[btnStyle="secondary"]:hover {{
        background-color: #232A42;
        border-color: #364161;
    }}

    QPushButton[btnStyle="danger"] {{
        background-color: rgba(239, 68, 68, 0.16);
        color: #FCA5A5;
        border: 1px solid rgba(239, 68, 68, 0.45);
        border-radius: 9px;
        padding: 9px 18px;
        font-weight: 700;
        font-size: 13px;
    }}

    QPushButton[btnStyle="danger"]:hover {{
        background-color: {ERROR};
        color: #FFFFFF;
        border-color: {ERROR};
    }}

    /* Segmented Pill Toggle Buttons */
    QPushButton[segment="true"] {{
        background-color: transparent;
        color: {TEXT_SECONDARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 8px;
        padding: 8px 12px;
        font-weight: 600;
        font-size: 12px;
    }}

    QPushButton[segment="true"]:hover {{
        color: {TEXT_MAIN};
        border-color: #3A4466;
    }}

    QPushButton[segment="true"]:checked {{
        background-color: rgba(46, 107, 255, 0.12);
        color: #FFFFFF;
        border: 1px solid {ACCENT_PRIMARY};
    }}

    /* Sliders */
    QSlider::groove:horizontal {{
        height: 6px;
        background: {BG_INPUT};
        border-radius: 3px;
        border: 1px solid {BORDER_SUBTLE};
    }}

    QSlider::sub-page:horizontal {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {ACCENT_PRIMARY},
            stop:1 {ACCENT_GLOW}
        );
        border-radius: 3px;
    }}

    QSlider::handle:horizontal {{
        background: #FFFFFF;
        border: 2px solid {ACCENT_PRIMARY};
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 9px;
    }}

    QSlider::handle:horizontal:hover {{
        background: {ACCENT_GLOW};
        border-color: #FFFFFF;
    }}

    /* SpinBox & ComboBox */
    QSpinBox, QComboBox {{
        background-color: {BG_INPUT};
        color: {TEXT_MAIN};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 8px;
        padding: 6px 10px;
        font-weight: 600;
        min-height: 20px;
    }}

    QSpinBox:focus, QComboBox:focus {{
        border-color: {ACCENT_PRIMARY};
    }}

    QSpinBox::up-button, QSpinBox::down-button {{
        width: 18px;
        background: transparent;
        border: none;
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {BG_CARD_ELEVATED};
        color: {TEXT_MAIN};
        border: 1px solid {BORDER_SUBTLE};
        selection-background-color: {ACCENT_PRIMARY};
        selection-color: #FFFFFF;
        outline: none;
        padding: 4px;
    }}

    /* RadioButton */
    QRadioButton {{
        color: {TEXT_MAIN};
        spacing: 8px;
        font-weight: 600;
    }}

    QRadioButton::indicator {{
        width: 14px;
        height: 14px;
        border-radius: 8px;
        border: 2px solid {TEXT_MUTED};
        background-color: transparent;
    }}

    QRadioButton::indicator:checked {{
        width: 8px;
        height: 8px;
        border-radius: 9px;
        border: 5px solid {ACCENT_PRIMARY};
        background-color: #FFFFFF;
    }}

    /* ScrollArea & ScrollBars */
    QScrollArea {{
        border: none;
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}

    QScrollBar::handle:vertical {{
        background: {BORDER_SUBTLE};
        border-radius: 4px;
        min-height: 24px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {TEXT_MUTED};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """
