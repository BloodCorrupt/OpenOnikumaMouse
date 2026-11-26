"""
Onikuma CW935 Gaming Mouse Desktop GUI (PySide6)
===============================================
A modern, dark-themed graphical user interface built with PySide6.
Supports full DPI control (50-12800), button remapping with interactive
mouse preview, live RGB lighting simulation, report rate, LOD, debounce time,
sleep timer, scroll direction, and battery monitoring.
"""

import sys
import os
import time
import signal
import threading
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QSize
from PySide6.QtGui import QIcon, QPixmap, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QGridLayout, QStackedWidget, QButtonGroup,
    QSlider, QSpinBox, QRadioButton, QComboBox, QScrollArea, QMessageBox,
    QSystemTrayIcon, QMenu, QSizePolicy
)

from .mouse import OnikumaCW935
from .protocol import (
    MouseConfig, ButtonAssignment,
    BUTTON_PRESETS, BUTTON_LABELS, DPI_MIN, DPI_MAX, DPI_STEP
)
from .device import find_devices
from .theme import (
    build_stylesheet, DPI_STAGE_COLORS,
    TEXT_MAIN, TEXT_SECONDARY, TEXT_MUTED, SUCCESS, ERROR, ACCENT_GLOW,
    BG_CARD_ELEVATED, BORDER_SUBTLE
)
from .widgets import (
    MousePreviewWidget, BatteryBadgeWidget, EffectCard, ToastNotification,
    make_nav_icon
)

logger = logging.getLogger(__name__)


class MouseSignalBridge(QObject):
    """Thread-safe signal bridge from background HID polling thread to Qt UI thread."""
    dpiRateChanged = Signal(int, int)
    batteryUpdated = Signal(int, bool)
    deviceFound = Signal()


class OnikumaMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Onikuma CW935 Mouse Control Panel")
        self.resize(1100, 740)
        self.setMinimumSize(980, 680)

        self.mouse: Optional[OnikumaCW935] = None
        self.is_connected = False
        self.current_config: Optional[MouseConfig] = None
        self.current_buttons: Optional[List[ButtonAssignment]] = None
        self._polling_active = True
        self._loading_ui = False
        self._force_quit = False

        self.signals = MouseSignalBridge()
        self.signals.dpiRateChanged.connect(self._update_realtime_dpi_and_rate)
        self.signals.batteryUpdated.connect(self._update_realtime_battery)
        self.signals.deviceFound.connect(self._try_connect_mouse)

        self._app_icon = self._load_app_icon()
        if not self._app_icon.isNull():
            self.setWindowIcon(self._app_icon)

        self._build_ui()
        self._init_tray_icon()

        # Connect on startup after event loop starts
        QTimer.singleShot(80, self._try_connect_mouse)

        # Start background thread for battery & real-time HID push reports
        self.poll_thread = threading.Thread(target=self._background_poll_loop, daemon=True)
        self.poll_thread.start()

    # ─── ASSETS & SYSTEM TRAY ──────────────────────────────────────────────────

    def _get_asset_path(self, filename: str) -> str:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, "assets", filename)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(base_dir)
        return os.path.join(project_dir, "assets", filename)

    def _load_app_icon(self) -> QIcon:
        ico_path = self._get_asset_path("icon.ico")
        png_path = self._get_asset_path("icon.png")
        if os.path.exists(ico_path):
            return QIcon(ico_path)
        if os.path.exists(png_path):
            return QIcon(png_path)
        return QIcon()

    def _init_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return

        icon = self._app_icon
        if icon.isNull():
            px = QPixmap(32, 32)
            px.fill(Qt.blue)
            icon = QIcon(px)

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Onikuma CW935 Mouse Control Panel")

        tray_menu = QMenu(self)
        act_show = QAction("Show Onikuma CW935", self)
        act_show.triggered.connect(self._restore_window)
        act_reconnect = QAction("Reconnect Mouse", self)
        act_reconnect.triggered.connect(self._try_connect_mouse)
        act_exit = QAction("Exit", self)
        act_exit.triggered.connect(self._exit_from_tray)

        tray_menu.addAction(act_show)
        tray_menu.addAction(act_reconnect)
        tray_menu.addSeparator()
        tray_menu.addAction(act_exit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self._restore_window()

    def _restore_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _exit_from_tray(self):
        self._force_quit = True
        self.close()

    def closeEvent(self, event):
        if not self._force_quit and self.tray_icon and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            return

        self._polling_active = False
        if hasattr(self, "btn_map_preview"):
            self.btn_map_preview._anim_timer.stop()
        if hasattr(self, "rgb_preview"):
            self.rgb_preview._anim_timer.stop()
        if self.mouse:
            try:
                self.mouse.disconnect()
            except Exception:
                pass
        if self.tray_icon:
            self.tray_icon.hide()
        event.accept()
        QApplication.quit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toast") and self.toast.isVisible():
            self.toast._reposition()

    # ─── UI CONSTRUCTION ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("CentralRoot")
        self.setCentralWidget(root)

        outer_layout = QVBoxLayout(root)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Top Header Bar
        outer_layout.addWidget(self._build_header_bar())

        # Body: Left Sidebar + Right Stacked Pages
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        body_layout.addWidget(self._build_sidebar())

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_page_dpi())
        self.pages.addWidget(self._build_page_buttons())
        self.pages.addWidget(self._build_page_rgb())
        self.pages.addWidget(self._build_page_info())
        body_layout.addWidget(self.pages, 1)

        outer_layout.addLayout(body_layout, 1)

        # Floating toast notification
        self.toast = ToastNotification(root)

    def _build_header_bar(self) -> QFrame:
        header = QFrame()
        header.setObjectName("HeaderBar")
        header.setFixedHeight(74)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(14)

        # Brand Title
        brand_col = QVBoxLayout()
        brand_col.setSpacing(1)
        lbl_title = QLabel("ONIKUMA  CW935")
        lbl_title.setStyleSheet(f"color: {TEXT_MAIN}; font-size: 19px; font-weight: 800; letter-spacing: 0.6px;")
        lbl_sub = QLabel("Instant S203 Sensor Control Suite")
        lbl_sub.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 500;")
        brand_col.addWidget(lbl_title)
        brand_col.addWidget(lbl_sub)
        layout.addLayout(brand_col)

        layout.addStretch(1)

        # Connection Status Pill
        self.lbl_status_badge = QLabel("● Disconnected")
        self.lbl_status_badge.setProperty("pill", True)
        self.lbl_status_badge.setStyleSheet(
            f"background-color: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35); "
            f"border-radius: 10px; padding: 6px 12px; color: {ERROR}; font-weight: 700; font-size: 12px;"
        )
        layout.addWidget(self.lbl_status_badge)

        # Battery Gauge Pill
        self.battery_badge = BatteryBadgeWidget()
        layout.addWidget(self.battery_badge)

        # Reconnect Button
        self.btn_reconnect = QPushButton("Reconnect")
        self.btn_reconnect.setProperty("btnStyle", "primary")
        self.btn_reconnect.setCursor(Qt.PointingHandCursor)
        self.btn_reconnect.clicked.connect(self._try_connect_mouse)
        layout.addWidget(self.btn_reconnect)

        return header

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 18)
        layout.setSpacing(6)

        nav_title = QLabel("NAVIGATION")
        nav_title.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1px; padding-left: 10px;")
        layout.addWidget(nav_title)
        layout.addSpacing(4)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        nav_items = [
            ("dpi", "  DPI && Performance", 0),
            ("buttons", "  Button Mapping", 1),
            ("rgb", "  RGB Lighting", 2),
            ("info", "  Device Info && Reset", 3),
        ]

        for icon_kind, label, page_idx in nav_items:
            btn = QPushButton(label)
            btn.setProperty("navButton", True)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIconSize(QSize(18, 18))
            idle_icon = make_nav_icon(icon_kind, TEXT_SECONDARY, 20)
            active_icon = make_nav_icon(icon_kind, ACCENT_GLOW, 20)
            btn.setIcon(active_icon if page_idx == 0 else idle_icon)
            btn.toggled.connect(
                lambda checked, b=btn, ai=active_icon, ii=idle_icon: b.setIcon(ai if checked else ii)
            )
            if page_idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, idx=page_idx: self.pages.setCurrentIndex(idx))
            self.nav_group.addButton(btn, page_idx)
            layout.addWidget(btn)

        layout.addStretch(1)

        # Live Telemetry Summary Card at bottom of sidebar
        summary_card = QFrame()
        summary_card.setProperty("subCard", True)
        sum_layout = QVBoxLayout(summary_card)
        sum_layout.setContentsMargins(12, 12, 12, 12)
        sum_layout.setSpacing(6)

        lbl_sum_hdr = QLabel("LIVE PROFILE")
        lbl_sum_hdr.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; border: none;")
        sum_layout.addWidget(lbl_sum_hdr)

        self.lbl_live_dpi = QLabel("Active DPI: --")
        self.lbl_live_dpi.setStyleSheet(f"color: {TEXT_MAIN}; font-size: 12px; font-weight: 700; border: none;")
        self.lbl_live_rate = QLabel("Polling: -- Hz")
        self.lbl_live_rate.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; border: none;")
        sum_layout.addWidget(self.lbl_live_dpi)
        sum_layout.addWidget(self.lbl_live_rate)

        layout.addWidget(summary_card)
        return sidebar

    # ─── PAGE 1: DPI & PERFORMANCE ─────────────────────────────────────────────

    def _build_page_dpi(self) -> QWidget:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        scroll.setWidget(content)

        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        main_layout = QGridLayout(content)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(16)
        main_layout.setColumnStretch(0, 11)
        main_layout.setColumnStretch(1, 9)

        # Left Card: DPI Stages
        dpi_card = QFrame()
        dpi_card.setProperty("card", True)
        dpi_layout = QVBoxLayout(dpi_card)
        dpi_layout.setContentsMargins(18, 16, 18, 16)
        dpi_layout.setSpacing(10)

        hdr = QLabel("DPI Stages")
        hdr.setProperty("heading", "section")
        sub = QLabel("Select active stage or drag sliders to tune sensitivity (50 – 12,800 DPI)")
        sub.setProperty("muted", True)
        sub.setWordWrap(True)
        dpi_layout.addWidget(hdr)
        dpi_layout.addWidget(sub)
        dpi_layout.addSpacing(4)

        self.dpi_stage_rows = []
        self.dpi_radio_group = QButtonGroup(self)
        self.dpi_radio_group.setExclusive(True)

        for i in range(6):
            color_name, color_hex = DPI_STAGE_COLORS[i]
            row_card = QFrame()
            row_card.setProperty("subCard", True)
            row_card.setProperty("activeStage", i == 0)
            row_layout = QHBoxLayout(row_card)
            row_layout.setContentsMargins(12, 10, 12, 10)
            row_layout.setSpacing(10)

            # Color dot
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(
                f"background-color: {color_hex}; border-radius: 6px; border: 1px solid rgba(255,255,255,0.3);"
            )
            row_layout.addWidget(dot)

            radio = QRadioButton(f"Stage {i+1} ({color_name})")
            radio.setFixedWidth(130)
            if i == 0:
                radio.setChecked(True)
            self.dpi_radio_group.addButton(radio, i)
            radio.clicked.connect(lambda checked, idx=i: self._on_active_dpi_selected(idx))
            row_layout.addWidget(radio)

            slider = QSlider(Qt.Horizontal)
            slider.setRange(DPI_MIN, DPI_MAX)
            slider.setSingleStep(DPI_STEP)
            slider.setPageStep(200)
            slider.setValue(800)
            row_layout.addWidget(slider, 1)

            spin = QSpinBox()
            spin.setRange(DPI_MIN, DPI_MAX)
            spin.setSingleStep(DPI_STEP)
            spin.setSuffix(" DPI")
            spin.setFixedWidth(98)
            spin.setValue(800)
            row_layout.addWidget(spin)

            # Sync slider <-> spinbox
            slider.valueChanged.connect(lambda val, idx=i: self._on_dpi_slider_moved(idx, val))
            spin.valueChanged.connect(lambda val, idx=i: self._on_dpi_spin_changed(idx, val))

            dpi_layout.addWidget(row_card)
            self.dpi_stage_rows.append({
                "card": row_card,
                "radio": radio,
                "slider": slider,
                "spin": spin,
                "color": color_hex,
            })

        dpi_layout.addStretch(1)

        btn_apply_dpi = QPushButton("Apply DPI Settings")
        btn_apply_dpi.setProperty("btnStyle", "primary")
        btn_apply_dpi.setCursor(Qt.PointingHandCursor)
        btn_apply_dpi.setFixedHeight(40)
        btn_apply_dpi.clicked.connect(self._apply_dpi_settings)
        dpi_layout.addWidget(btn_apply_dpi)

        main_layout.addWidget(dpi_card, 0, 0)

        # Right Card: Performance & Tuning
        perf_card = QFrame()
        perf_card.setProperty("card", True)
        perf_layout = QVBoxLayout(perf_card)
        perf_layout.setContentsMargins(20, 18, 20, 18)
        perf_layout.setSpacing(14)

        perf_hdr = QLabel("Performance & Sensor Tuning")
        perf_hdr.setProperty("heading", "section")
        perf_sub = QLabel("Configure polling rate, lift-off distance, debounce, and sleep behavior")
        perf_sub.setProperty("muted", True)
        perf_sub.setWordWrap(True)
        perf_layout.addWidget(perf_hdr)
        perf_layout.addWidget(perf_sub)

        # 1. USB Polling Rate
        perf_layout.addWidget(self._make_field_label("USB Polling Rate"))
        rate_row = QHBoxLayout()
        rate_row.setSpacing(8)
        self.rate_group = QButtonGroup(self)
        self.rate_group.setExclusive(True)
        self.rate_buttons = {}
        for hz in (125, 250, 500, 1000):
            btn = QPushButton(f"{hz} Hz")
            btn.setProperty("segment", True)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, val=hz: self._on_report_rate_changed(val))
            self.rate_group.addButton(btn, hz)
            self.rate_buttons[hz] = btn
            rate_row.addWidget(btn)
        self.rate_buttons[1000].setChecked(True)
        perf_layout.addLayout(rate_row)

        # 2. Lift-Off Distance (LOD)
        perf_layout.addWidget(self._make_field_label("Lift-Off Distance (LOD)"))
        lod_row = QHBoxLayout()
        lod_row.setSpacing(8)
        self.lod_group = QButtonGroup(self)
        self.lod_group.setExclusive(True)
        self.btn_lod_low = QPushButton("Low (1 mm)")
        self.btn_lod_high = QPushButton("High (2 mm)")
        for level, btn in ((1, self.btn_lod_low), (2, self.btn_lod_high)):
            btn.setProperty("segment", True)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, lv=level: self._on_lod_changed(lv))
            self.lod_group.addButton(btn, level)
            lod_row.addWidget(btn)
        self.btn_lod_low.setChecked(True)
        perf_layout.addLayout(lod_row)

        # 3. Button Debounce Delay
        deb_hdr = QHBoxLayout()
        deb_hdr.addWidget(self._make_field_label("Button Debounce Delay"))
        deb_hdr.addStretch(1)
        self.lbl_debounce_val = QLabel("8 ms")
        self.lbl_debounce_val.setProperty("pill", True)
        deb_hdr.addWidget(self.lbl_debounce_val)
        perf_layout.addLayout(deb_hdr)

        self.slider_debounce = QSlider(Qt.Horizontal)
        self.slider_debounce.setRange(1, 30)
        self.slider_debounce.setValue(8)
        self.slider_debounce.valueChanged.connect(
            lambda v: self.lbl_debounce_val.setText(f"{v} ms")
        )
        self.slider_debounce.sliderReleased.connect(self._on_debounce_committed)
        perf_layout.addWidget(self.slider_debounce)

        # 4. Auto-Sleep Timeout
        slp_hdr = QHBoxLayout()
        slp_hdr.addWidget(self._make_field_label("Auto-Sleep Timeout"))
        slp_hdr.addStretch(1)
        self.lbl_sleep_val = QLabel("10 min")
        self.lbl_sleep_val.setProperty("pill", True)
        slp_hdr.addWidget(self.lbl_sleep_val)
        perf_layout.addLayout(slp_hdr)

        self.slider_sleep = QSlider(Qt.Horizontal)
        self.slider_sleep.setRange(0, 30)
        self.slider_sleep.setValue(10)
        self.slider_sleep.valueChanged.connect(
            lambda v: self.lbl_sleep_val.setText(f"{v} min" if v > 0 else "Off")
        )
        self.slider_sleep.sliderReleased.connect(self._on_sleep_committed)
        perf_layout.addWidget(self.slider_sleep)

        # 5. Scroll Wheel Direction
        roller_card = QFrame()
        roller_card.setProperty("subCard", True)
        roller_layout = QVBoxLayout(roller_card)
        roller_layout.setContentsMargins(14, 12, 14, 12)
        roller_layout.setSpacing(8)

        roller_title = QLabel("Scroll Wheel Direction")
        roller_title.setStyleSheet(f"color: {TEXT_MAIN}; font-weight: 700; font-size: 13px; border: none;")
        roller_desc = QLabel("Switch mouse wheel up and down scroll direction")
        roller_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; border: none;")
        roller_layout.addWidget(roller_title)
        roller_layout.addWidget(roller_desc)

        scroll_btn_row = QHBoxLayout()
        scroll_btn_row.setSpacing(8)
        self.scroll_group = QButtonGroup(self)
        self.scroll_group.setExclusive(True)
        self.btn_scroll_fwd = QPushButton("Forward (Normal)")
        self.btn_scroll_rev = QPushButton("Reverse (Inverted)")
        for val, btn in ((0, self.btn_scroll_fwd), (1, self.btn_scroll_rev)):
            btn.setProperty("segment", True)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, d=val: self._on_scroll_direction_changed(d))
            self.scroll_group.addButton(btn, val)
            scroll_btn_row.addWidget(btn)
        self.btn_scroll_fwd.setChecked(True)
        roller_layout.addLayout(scroll_btn_row)

        perf_layout.addWidget(roller_card)
        perf_layout.addStretch(1)

        main_layout.addWidget(perf_card, 0, 1)
        return page

    # ─── PAGE 2: BUTTON MAPPING ────────────────────────────────────────────────

    def _build_page_buttons(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)
        layout.setColumnStretch(0, 5)
        layout.setColumnStretch(1, 7)

        # Left Card: Interactive Mouse Diagram
        preview_card = QFrame()
        preview_card.setProperty("card", True)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(18, 18, 18, 18)
        preview_layout.setSpacing(8)

        lbl_p_hdr = QLabel("Interactive Mouse Map")
        lbl_p_hdr.setProperty("heading", "section")
        lbl_p_sub = QLabel("Click a button zone to highlight its assignment")
        lbl_p_sub.setProperty("muted", True)
        preview_layout.addWidget(lbl_p_hdr)
        preview_layout.addWidget(lbl_p_sub)

        self.btn_map_preview = MousePreviewWidget(interactive=True)
        self.btn_map_preview.buttonClicked.connect(self._on_mouse_diagram_clicked)
        preview_layout.addWidget(self.btn_map_preview, 1)

        layout.addWidget(preview_card, 0, 0)

        # Right Card: 6 Programmable Button Rows
        map_card = QFrame()
        map_card.setProperty("card", True)
        map_layout = QVBoxLayout(map_card)
        map_layout.setContentsMargins(20, 18, 20, 18)
        map_layout.setSpacing(10)

        lbl_m_hdr = QLabel("Programmable Mouse Buttons")
        lbl_m_hdr.setProperty("heading", "section")
        lbl_m_sub = QLabel("Assign mouse functions, media controls, or disable individual buttons")
        lbl_m_sub.setProperty("muted", True)
        map_layout.addWidget(lbl_m_hdr)
        map_layout.addWidget(lbl_m_sub)
        map_layout.addSpacing(4)

        preset_names = [name.replace("_", " ").title() for name in BUTTON_PRESETS.keys()]
        self.btn_combo_widgets: list[QComboBox] = []
        self.btn_row_cards: list[QFrame] = []

        for i in range(6):
            row_card = QFrame()
            row_card.setProperty("subCard", True)
            row_card.setProperty("activeStage", False)
            row_layout = QHBoxLayout(row_card)
            row_layout.setContentsMargins(14, 10, 14, 10)
            row_layout.setSpacing(12)

            lbl_text = BUTTON_LABELS[i] if i < len(BUTTON_LABELS) else f"Button {i+1}"
            lbl = QLabel(f"{i+1}.  {lbl_text}")
            lbl.setFixedWidth(155)
            lbl.setStyleSheet(f"color: {TEXT_MAIN}; font-weight: 700; font-size: 13px; border: none;")
            row_layout.addWidget(lbl)

            combo = QComboBox()
            combo.addItems(preset_names)
            combo.setCursor(Qt.PointingHandCursor)
            combo.highlighted.connect(lambda _idx, b=i: self.btn_map_preview.set_selected_button(b))
            row_layout.addWidget(combo, 1)

            map_layout.addWidget(row_card)
            self.btn_combo_widgets.append(combo)
            self.btn_row_cards.append(row_card)

        map_layout.addStretch(1)

        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        btn_save_map = QPushButton("Save Button Mapping")
        btn_save_map.setProperty("btnStyle", "primary")
        btn_save_map.setCursor(Qt.PointingHandCursor)
        btn_save_map.setFixedHeight(40)
        btn_save_map.clicked.connect(self._apply_button_mapping)

        btn_reset_map = QPushButton("Reset to Factory Defaults")
        btn_reset_map.setProperty("btnStyle", "secondary")
        btn_reset_map.setCursor(Qt.PointingHandCursor)
        btn_reset_map.setFixedHeight(40)
        btn_reset_map.clicked.connect(self._reset_buttons_to_default)

        action_row.addWidget(btn_save_map, 1)
        action_row.addWidget(btn_reset_map, 1)
        map_layout.addLayout(action_row)

        layout.addWidget(map_card, 0, 1)
        return page

    # ─── PAGE 3: RGB LIGHTING ──────────────────────────────────────────────────

    def _build_page_rgb(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)
        layout.setColumnStretch(0, 5)
        layout.setColumnStretch(1, 8)

        # Left Card: Live RGB Simulation Preview
        sim_card = QFrame()
        sim_card.setProperty("card", True)
        sim_layout = QVBoxLayout(sim_card)
        sim_layout.setContentsMargins(18, 18, 18, 18)
        sim_layout.setSpacing(8)

        lbl_s_hdr = QLabel("Live RGB Preview")
        lbl_s_hdr.setProperty("heading", "section")
        lbl_s_sub = QLabel("Real-time preview of the active lighting effect")
        lbl_s_sub.setProperty("muted", True)
        sim_layout.addWidget(lbl_s_hdr)
        sim_layout.addWidget(lbl_s_sub)

        self.rgb_preview = MousePreviewWidget(interactive=False)
        sim_layout.addWidget(self.rgb_preview, 1)

        layout.addWidget(sim_card, 0, 0)

        # Right Card: Effect Selector Grid
        fx_card = QFrame()
        fx_card.setProperty("card", True)
        fx_layout = QVBoxLayout(fx_card)
        fx_layout.setContentsMargins(20, 18, 20, 18)
        fx_layout.setSpacing(12)

        top_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_f_hdr = QLabel("Lighting Effects")
        lbl_f_hdr.setProperty("heading", "section")
        lbl_f_sub = QLabel("Click any effect card to apply it immediately to your mouse")
        lbl_f_sub.setProperty("muted", True)
        title_col.addWidget(lbl_f_hdr)
        title_col.addWidget(lbl_f_sub)
        top_row.addLayout(title_col, 1)

        self.light_modes_list = [
            (0, "Wave", "Flowing multi-color spectrum", ["#3B82F6", "#06B6D4", "#EC4899"]),
            (1, "Neon", "Smooth full-spectrum color cycle", ["#10B981", "#3B82F6", "#A855F7"]),
            (2, "Touring Flash", "Dynamic energetic strobe sweep", ["#F59E0B", "#EF4444"]),
            (3, "YOYO Ball", "Dual-tone oscillating pulse", ["#06B6D4", "#EC4899"]),
            (4, "Unidirectional Flashing", "Sharp directional pulse", ["#3B82F6", "#00D2FF"]),
            (5, "Circular Breathing", "Gentle rhythmic fade in & out", ["#6366F1", "#38BDF8"]),
            (6, "Turn Off The Light", "Disable all LEDs to save battery", ["#1E293B", "#0F172A"]),
        ]

        self.combo_light_mode = QComboBox()
        self.combo_light_mode.addItems([m[1] for m in self.light_modes_list])
        self.combo_light_mode.setFixedWidth(200)
        self.combo_light_mode.currentIndexChanged.connect(self._on_light_combo_changed)
        top_row.addWidget(self.combo_light_mode)
        fx_layout.addLayout(top_row)

        grid = QGridLayout()
        grid.setSpacing(10)
        self.effect_cards: dict[int, EffectCard] = {}

        for idx, (mode_id, name, desc, colors) in enumerate(self.light_modes_list):
            card = EffectCard(mode_id, name, desc, colors)
            card.clicked.connect(self._on_light_mode_selected)
            self.effect_cards[mode_id] = card
            grid.addWidget(card, idx // 2, idx % 2)

        fx_layout.addLayout(grid)
        fx_layout.addStretch(1)

        # Static Color Hardware Note
        note_card = QFrame()
        note_card.setProperty("subCard", True)
        note_layout = QVBoxLayout(note_card)
        note_layout.setContentsMargins(14, 12, 14, 12)
        note_layout.setSpacing(6)

        note_hdr = QLabel("ℹ  Static Color & DPI Stage Sync")
        note_hdr.setStyleSheet(f"color: {TEXT_MAIN}; font-weight: 700; font-size: 12px; border: none;")
        note_body = QLabel(
            "On Onikuma CW935 hardware, static solid LED colors correspond to DPI Stages 1–6 "
            "(Blue, Green, Yellow, Cyan, Magenta, White). Select your active DPI stage to change the static color."
        )
        note_body.setWordWrap(True)
        note_body.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; border: none;")
        note_layout.addWidget(note_hdr)
        note_layout.addWidget(note_body)

        fx_layout.addWidget(note_card)
        layout.addWidget(fx_card, 0, 1)
        return page

    # ─── PAGE 4: DEVICE INFO & RESET ───────────────────────────────────────────

    def _build_page_info(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)

        # Hardware Diagnostics Card
        info_card = QFrame()
        info_card.setProperty("card", True)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(22, 20, 22, 20)
        info_layout.setSpacing(14)

        lbl_i_hdr = QLabel("Hardware Diagnostics & Details")
        lbl_i_hdr.setProperty("heading", "section")
        lbl_i_sub = QLabel("Live device identification, firmware version, and connection interface")
        lbl_i_sub.setProperty("muted", True)
        info_layout.addWidget(lbl_i_hdr)
        info_layout.addWidget(lbl_i_sub)

        diag_grid = QGridLayout()
        diag_grid.setSpacing(10)
        self.diag_labels: dict[str, QLabel] = {}

        fields = [
            ("model", "Model Name", "Onikuma CW935"),
            ("sensor", "Optical Sensor", "Instant S203 (12,800 DPI)"),
            ("firmware", "Firmware Version", "--"),
            ("vid", "Vendor ID (VID)", "--"),
            ("pid", "Product ID (PID)", "--"),
            ("mode", "Interface Mode", "Disconnected"),
        ]

        for idx, (key, title, default_val) in enumerate(fields):
            cell = QFrame()
            cell.setProperty("subCard", True)
            cell_l = QVBoxLayout(cell)
            cell_l.setContentsMargins(14, 10, 14, 10)
            cell_l.setSpacing(3)

            lbl_k = QLabel(title.upper())
            lbl_k.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 0.7px; border: none;")
            lbl_v = QLabel(default_val)
            lbl_v.setStyleSheet(f"color: {TEXT_MAIN}; font-size: 13px; font-weight: 700; border: none;")

            cell_l.addWidget(lbl_k)
            cell_l.addWidget(lbl_v)
            diag_grid.addWidget(cell, idx // 3, idx % 3)
            self.diag_labels[key] = lbl_v

        info_layout.addLayout(diag_grid)
        layout.addWidget(info_card)

        # Factory Reset Card
        reset_card = QFrame()
        reset_card.setProperty("card", True)
        reset_layout = QVBoxLayout(reset_card)
        reset_layout.setContentsMargins(22, 20, 22, 20)
        reset_layout.setSpacing(10)

        lbl_r_hdr = QLabel("Factory Reset")
        lbl_r_hdr.setStyleSheet(f"color: {ERROR}; font-size: 16px; font-weight: 700;")
        lbl_r_desc = QLabel(
            "Wipe onboard mouse memory and restore all DPI stages, button assignments, "
            "RGB lighting effects, and performance tuning to original factory defaults."
        )
        lbl_r_desc.setWordWrap(True)
        lbl_r_desc.setProperty("muted", True)

        btn_reset = QPushButton("Restore All Factory Defaults")
        btn_reset.setProperty("btnStyle", "danger")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setFixedWidth(240)
        btn_reset.setFixedHeight(40)
        btn_reset.clicked.connect(self._factory_reset)

        reset_layout.addWidget(lbl_r_hdr)
        reset_layout.addWidget(lbl_r_desc)
        reset_layout.addSpacing(6)
        reset_layout.addWidget(btn_reset)

        layout.addWidget(reset_card)
        layout.addStretch(1)
        return page

    # ─── HELPERS ───────────────────────────────────────────────────────────────

    def _make_field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {TEXT_MAIN}; font-size: 13px; font-weight: 700;")
        return lbl

    def _repolish(self, widget: QWidget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _highlight_active_dpi_card(self, active_idx: int):
        for i, row in enumerate(self.dpi_stage_rows):
            row["card"].setProperty("activeStage", i == active_idx)
            self._repolish(row["card"])
        if 0 <= active_idx < len(DPI_STAGE_COLORS):
            hex_col = DPI_STAGE_COLORS[active_idx][1]
            self.rgb_preview.set_dpi_color(hex_col)
            self.btn_map_preview.set_dpi_color(hex_col)

    def _update_live_profile_summary(self):
        if not self.current_config:
            self.lbl_live_dpi.setText("Active DPI: --")
            self.lbl_live_rate.setText("Polling: -- Hz")
            return
        idx = self.current_config.dpi_index
        dpi_val = self.dpi_stage_rows[idx]["spin"].value() if 0 <= idx < 6 else self.current_config.active_dpi
        self.lbl_live_dpi.setText(f"Active DPI: {dpi_val:,}")
        self.lbl_live_rate.setText(f"Polling: {self.current_config.report_rate_hz} Hz")

    # ─── HARDWARE CONNECTIVITY & SYNC ──────────────────────────────────────────

    def _try_connect_mouse(self):
        try:
            if not self.mouse:
                self.mouse = OnikumaCW935()
            self.mouse.connect()
            self.mouse.register_callback(self._on_realtime_event)
            self.is_connected = True
            self._update_connection_status_ui(True)
            self._load_config_from_mouse()
            self.toast.show_message("Mouse connected successfully", "success")
        except Exception as e:
            logger.warning(f"Connection failed: {e}")
            self.mouse = None
            self.is_connected = False
            self._update_connection_status_ui(False)

    def _on_realtime_event(self, event_data: dict):
        event_type = event_data.get("event")
        if event_type == "dpi_rate_changed":
            dpi_idx = event_data.get("dpi_index", 0)
            rate_idx = event_data.get("report_rate", 3)
            self.signals.dpiRateChanged.emit(dpi_idx, rate_idx)
        elif event_type == "battery_updated":
            bat = event_data.get("battery")
            if bat:
                self.signals.batteryUpdated.emit(bat.percentage, bat.charging)

    def _update_realtime_dpi_and_rate(self, dpi_idx: int, rate_idx: int):
        self._loading_ui = True
        try:
            if 0 <= dpi_idx < len(self.dpi_stage_rows):
                self.dpi_stage_rows[dpi_idx]["radio"].setChecked(True)
                self._highlight_active_dpi_card(dpi_idx)
                if self.current_config:
                    self.current_config.dpi_index = dpi_idx
            hz_map = {0: 125, 1: 250, 2: 500, 3: 1000}
            hz = hz_map.get(rate_idx)
            if hz and hz in self.rate_buttons:
                self.rate_buttons[hz].setChecked(True)
                if self.current_config:
                    self.current_config.report_rate = rate_idx
            self._update_live_profile_summary()
        finally:
            self._loading_ui = False

    def _update_realtime_battery(self, pct: int, charging: bool):
        self.battery_badge.set_battery(pct, charging)

    def _update_connection_status_ui(self, connected: bool):
        if connected and self.mouse:
            info = self.mouse.get_info()
            self.lbl_status_badge.setText(f"● Connected ({info.connection_mode})")
            self.lbl_status_badge.setStyleSheet(
                f"background-color: rgba(16, 185, 129, 0.14); border: 1px solid rgba(16, 185, 129, 0.4); "
                f"border-radius: 10px; padding: 6px 12px; color: {SUCCESS}; font-weight: 700; font-size: 12px;"
            )
            self.diag_labels["firmware"].setText(info.firmware_version)
            self.diag_labels["vid"].setText(f"0x{info.vendor_id:04X}")
            self.diag_labels["pid"].setText(f"0x{info.product_id:04X}")
            self.diag_labels["mode"].setText(info.connection_mode)
        else:
            self.lbl_status_badge.setText("● Disconnected")
            self.lbl_status_badge.setStyleSheet(
                f"background-color: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35); "
                f"border-radius: 10px; padding: 6px 12px; color: {ERROR}; font-weight: 700; font-size: 12px;"
            )
            self.battery_badge.set_battery(None, False)
            self.diag_labels["firmware"].setText("--")
            self.diag_labels["vid"].setText("--")
            self.diag_labels["pid"].setText("--")
            self.diag_labels["mode"].setText("No device detected")
            self._update_live_profile_summary()

    def _load_config_from_mouse(self):
        if not self.is_connected or not self.mouse:
            return

        self._loading_ui = True
        try:
            self.current_config = self.mouse.get_config()
            self.current_buttons = self.mouse.get_buttons()
            cfg = self.current_config

            # DPI stages
            active_idx = max(0, min(5, cfg.dpi_index))
            self.dpi_stage_rows[active_idx]["radio"].setChecked(True)
            self._highlight_active_dpi_card(active_idx)

            for i in range(6):
                val = cfg.dpi_values[i] if i < len(cfg.dpi_values) else 800
                self.dpi_stage_rows[i]["slider"].setValue(val)
                self.dpi_stage_rows[i]["spin"].setValue(val)

            # Report rate
            hz = cfg.report_rate_hz
            if hz in self.rate_buttons:
                self.rate_buttons[hz].setChecked(True)

            # LOD
            if cfg.lod_value == 2:
                self.btn_lod_high.setChecked(True)
            else:
                self.btn_lod_low.setChecked(True)

            # Debounce & Sleep
            self.slider_debounce.setValue(cfg.key_respond)
            self.lbl_debounce_val.setText(f"{cfg.key_respond} ms")

            self.slider_sleep.setValue(cfg.sleep_time)
            self.lbl_sleep_val.setText(f"{cfg.sleep_time} min" if cfg.sleep_time else "Off")

            # Scroll direction
            if cfg.scroll_flag:
                self.btn_scroll_rev.setChecked(True)
            else:
                self.btn_scroll_fwd.setChecked(True)

            # Buttons
            for i, btn in enumerate(self.current_buttons[:6]):
                matching_preset = "disabled"
                for p_key, (p_type, p_c1, p_c2, _p_c3) in BUTTON_PRESETS.items():
                    if btn.type == p_type and btn.code1 == p_c1 and btn.code2 == p_c2:
                        matching_preset = p_key
                        break
                preset_display = matching_preset.replace("_", " ").title()
                self.btn_combo_widgets[i].setCurrentText(preset_display)

            # RGB Lighting
            self._sync_rgb_selection_ui(cfg.light_mode)

            # Battery
            bat = self.mouse.get_battery(force_refresh=True)
            self.battery_badge.set_battery(bat.percentage, bat.charging)
            self._update_live_profile_summary()

        except Exception as e:
            logger.error(f"Error loading mouse configuration: {e}")
        finally:
            self._loading_ui = False

    def _sync_rgb_selection_ui(self, mode_id: int):
        for m_id, card in self.effect_cards.items():
            card.set_selected(m_id == mode_id)
        for idx, (m_id, _name, _desc, _cols) in enumerate(self.light_modes_list):
            if m_id == mode_id:
                self.combo_light_mode.setCurrentIndex(idx)
                break
        self.rgb_preview.set_light_mode(mode_id)
        self.btn_map_preview.set_light_mode(mode_id)

    # ─── EVENT HANDLERS ────────────────────────────────────────────────────────

    def _on_active_dpi_selected(self, idx: int):
        self._highlight_active_dpi_card(idx)
        if self.current_config:
            self.current_config.dpi_index = idx
        self._update_live_profile_summary()
        if not self._loading_ui and self.is_connected and self.mouse:
            self.mouse.set_active_dpi_stage(idx)

    def _on_dpi_slider_moved(self, idx: int, val: int):
        snapped = round(val / DPI_STEP) * DPI_STEP
        snapped = max(DPI_MIN, min(DPI_MAX, snapped))
        spin = self.dpi_stage_rows[idx]["spin"]
        if spin.value() != snapped:
            spin.blockSignals(True)
            spin.setValue(snapped)
            spin.blockSignals(False)
        self._update_live_profile_summary()

    def _on_dpi_spin_changed(self, idx: int, val: int):
        slider = self.dpi_stage_rows[idx]["slider"]
        if slider.value() != val:
            slider.blockSignals(True)
            slider.setValue(val)
            slider.blockSignals(False)
        self._update_live_profile_summary()

    def _apply_dpi_settings(self):
        if not self.is_connected or not self.mouse:
            self.toast.show_message("Mouse not connected", "warning")
            return
        stages = [row["spin"].value() for row in self.dpi_stage_rows]
        active_idx = max(0, self.dpi_radio_group.checkedId())
        self.current_config = self.mouse.set_dpi_stages(stages, active_index=active_idx)
        self._update_live_profile_summary()
        self.toast.show_message("DPI settings saved to onboard memory", "success")

    def _on_report_rate_changed(self, hz: int):
        if self._loading_ui or not self.is_connected or not self.mouse:
            return
        self.current_config = self.mouse.set_report_rate(hz)
        self._update_live_profile_summary()
        self.toast.show_message(f"Polling rate set to {hz} Hz", "info")

    def _on_lod_changed(self, level: int):
        if self._loading_ui or not self.is_connected or not self.mouse:
            return
        self.current_config = self.mouse.set_lod(level)
        self.toast.show_message(f"Lift-off distance set to {'Low (1 mm)' if level == 1 else 'High (2 mm)'}", "info")

    def _on_debounce_committed(self):
        if self._loading_ui or not self.is_connected or not self.mouse:
            return
        ms = self.slider_debounce.value()
        self.current_config = self.mouse.set_debounce(ms)
        self.toast.show_message(f"Debounce delay set to {ms} ms", "info")

    def _on_sleep_committed(self):
        if self._loading_ui or not self.is_connected or not self.mouse:
            return
        mins = self.slider_sleep.value()
        self.current_config = self.mouse.set_sleep_timer(mins)
        msg = f"Auto-sleep set to {mins} min" if mins else "Auto-sleep disabled"
        self.toast.show_message(msg, "info")

    def _on_scroll_direction_changed(self, direction: int):
        if self._loading_ui or not self.is_connected or not self.mouse:
            return
        self.current_config = self.mouse.set_scroll_direction(direction)
        self.toast.show_message(
            f"Scroll direction: {'Reverse' if direction else 'Forward'}", "info"
        )

    def _on_mouse_diagram_clicked(self, btn_idx: int):
        for i, card in enumerate(self.btn_row_cards):
            card.setProperty("activeStage", i == btn_idx)
            self._repolish(card)
        if 0 <= btn_idx < len(self.btn_combo_widgets):
            self.btn_combo_widgets[btn_idx].setFocus()

    def _apply_button_mapping(self):
        if not self.is_connected or not self.mouse:
            self.toast.show_message("Mouse not connected", "warning")
            return
        for i, combo in enumerate(self.btn_combo_widgets[:6]):
            preset_key = combo.currentText().lower().replace(" ", "_")
            if preset_key in BUTTON_PRESETS:
                self.mouse.set_button_preset(i, preset_key)
        self.toast.show_message("Button mapping saved to onboard memory", "success")

    def _reset_buttons_to_default(self):
        if not self.is_connected or not self.mouse:
            self.toast.show_message("Mouse not connected", "warning")
            return
        self.mouse.reset_buttons()
        self._load_config_from_mouse()
        self.toast.show_message("Buttons restored to factory defaults", "success")

    def _on_light_combo_changed(self, combo_idx: int):
        if self._loading_ui or combo_idx < 0 or combo_idx >= len(self.light_modes_list):
            return
        mode_id = self.light_modes_list[combo_idx][0]
        self._on_light_mode_selected(mode_id)

    def _on_light_mode_selected(self, mode_id: int):
        self._loading_ui = True
        try:
            self._sync_rgb_selection_ui(mode_id)
        finally:
            self._loading_ui = False

        if self.is_connected and self.mouse:
            self.current_config = self.mouse.set_light_mode(mode_id)

    def _factory_reset(self):
        if not self.is_connected or not self.mouse:
            self.toast.show_message("Mouse not connected", "warning")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Factory Reset",
            "Are you sure you want to restore ALL mouse settings and button mappings to factory defaults?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.mouse.factory_reset()
            self._load_config_from_mouse()
            self.toast.show_message("All mouse settings restored to factory defaults", "success")

    # ─── BACKGROUND POLLING ────────────────────────────────────────────────────

    def _background_poll_loop(self):
        tick_counter = 0
        while self._polling_active:
            time.sleep(0.02)  # 50Hz
            tick_counter += 1

            if self.is_connected and self.mouse:
                try:
                    self.mouse.poll_events()
                except Exception as e:
                    logger.debug(f"Error in background poll: {e}")
            elif not self.is_connected and tick_counter >= 100:
                tick_counter = 0
                try:
                    if find_devices():
                        self.signals.deviceFound.emit()
                except Exception as e:
                    logger.debug(f"Error scanning devices: {e}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(build_stylesheet())

    window = OnikumaMainWindow()

    # Allow Ctrl+C in terminal to exit cleanly without KeyboardInterrupt spam
    signal.signal(signal.SIGINT, lambda *_args: window._exit_from_tray())
    sigint_timer = QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
