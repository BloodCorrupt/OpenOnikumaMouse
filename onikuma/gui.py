"""
Onikuma CW935 Gaming Mouse Desktop GUI
=======================================
A modern, dark-themed graphical user interface built with CustomTkinter.
Supports full DPI control (50-12800), button remapping, RGB lighting,
report rate, debounce time, sleep timer, and battery monitoring.
"""

import sys
import os
import time
import threading
import logging
from typing import Optional, List

import customtkinter as ctk  # type: ignore
from tkinter import messagebox

from .mouse import OnikumaCW935
from .protocol import (
    MouseConfig, ButtonAssignment, ReportRate, ButtonType,
    BUTTON_PRESETS, BUTTON_LABELS, DPI_MIN, DPI_MAX, DPI_STEP,
    LightMode
)
from .device import find_devices

logger = logging.getLogger(__name__)

# System Appearance & Color Palette
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

COLOR_BG_DARK = "#12131C"
COLOR_CARD_BG = "#1E1F2E"
COLOR_ACCENT = "#0066FF"
COLOR_ACCENT_HOVER = "#0052CC"
COLOR_TEXT_MAIN = "#FFFFFF"
COLOR_TEXT_MUTED = "#8A8D9F"
COLOR_SUCCESS = "#00E676"
COLOR_WARNING = "#FFB300"
COLOR_ERROR = "#FF5252"


class OnikumaGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Onikuma CW935 Mouse Control Panel")
        self.geometry("960 x 720")
        self.minsize(900, 680)
        self.configure(fg_color=COLOR_BG_DARK)

        self.mouse: Optional[OnikumaCW935] = None
        self.is_connected = False
        self.current_config: Optional[MouseConfig] = None
        self.current_buttons: Optional[List[ButtonAssignment]] = None
        self._polling_active = True

        self._build_ui()
        self._try_connect_mouse()

        # Start background thread for battery & connection updates
        self.poll_thread = threading.Thread(target=self._background_poll_loop, daemon=True)
        self.poll_thread.start()

    def _build_ui(self):
        """Construct all GUI frames, header, tabs, and widgets."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ─── HEADER FRAME ────────────────────────────────────────────────────────
        self.header_frame = ctk.CTkFrame(self, fg_color=COLOR_CARD_BG, corner_radius=12, height=90)
        self.header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        self.header_frame.grid_columnconfigure(1, weight=1)

        # Logo / Title
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="ONIKUMA  CW935",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(15, 0), sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            self.header_frame,
            text="Instant S203 Sensor Driver Utility",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED
        )
        self.subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        # Status indicators (Center/Right)
        self.status_container = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.status_container.grid(row=0, column=2, rowspan=2, padx=20, pady=10, sticky="e")

        self.status_indicator = ctk.CTkLabel(
            self.status_container,
            text="● Disconnected",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_ERROR
        )
        self.status_indicator.pack(side="left", padx=10)

        self.battery_label = ctk.CTkLabel(
            self.status_container,
            text="Battery: --%",
            font=ctk.CTkFont(size=14),
            text_color=COLOR_TEXT_MUTED
        )
        self.battery_label.pack(side="left", padx=10)

        self.btn_refresh = ctk.CTkButton(
            self.status_container,
            text="Reconnect",
            width=100,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            command=self._try_connect_mouse
        )
        self.btn_refresh.pack(side="left", padx=10)

        # ─── TAB NAVIGATION ──────────────────────────────────────────────────────
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=COLOR_CARD_BG,
            segmented_button_fg_color=COLOR_BG_DARK,
            segmented_button_selected_color=COLOR_ACCENT,
            segmented_button_selected_hover_color=COLOR_ACCENT_HOVER,
            corner_radius=12
        )
        self.tabview.grid(row=1, column=0, padx=20, pady=(10, 20), sticky="nsew")

        self.tab_dpi = self.tabview.add("DPI & Performance")
        self.tab_buttons = self.tabview.add("Button Mapping")
        self.tab_rgb = self.tabview.add("RGB Lighting")
        self.tab_info = self.tabview.add("Device Info & Reset")

        self._build_tab_dpi()
        self._build_tab_buttons()
        self._build_tab_rgb()
        self._build_tab_info()

    # ─── TAB 1: DPI & PERFORMANCE ────────────────────────────────────────────────

    def _build_tab_dpi(self):
        tab = self.tab_dpi
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)

        # Left Column: DPI Stages
        dpi_frame = ctk.CTkFrame(tab, fg_color="transparent")
        dpi_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")

        ctk.CTkLabel(
            dpi_frame, text="DPI Stages (50 - 12,800 DPI)",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=COLOR_TEXT_MAIN
        ).pack(anchor="w", pady=(0, 10))

        self.dpi_widgets = []
        self.active_dpi_var = ctk.IntVar(value=0)

        stage_color_names = ["Red", "Green", "Blue", "Yellow", "Cyan", "Purple"]

        for i in range(6):
            stage_row = ctk.CTkFrame(dpi_frame, fg_color=COLOR_BG_DARK, corner_radius=8)
            stage_row.pack(fill="x", pady=4)
            stage_row.grid_columnconfigure(2, weight=1)

            c_name = stage_color_names[i] if i < len(stage_color_names) else ""
            r_btn = ctk.CTkRadioButton(
                stage_row, text=f"Stage {i+1} ({c_name})",
                variable=self.active_dpi_var, value=i,
                command=self._on_active_dpi_radio_change,
                fg_color=COLOR_ACCENT
            )
            r_btn.grid(row=0, column=0, padx=10, pady=8)

            slider = ctk.CTkSlider(
                stage_row, from_=DPI_MIN, to=DPI_MAX, number_of_steps=255,
                button_color=COLOR_ACCENT, button_hover_color=COLOR_ACCENT_HOVER,
                command=lambda val, idx=i: self._on_dpi_slider_change(idx, val)
            )
            slider.grid(row=0, column=2, padx=10, pady=8, sticky="ew")

            entry = ctk.CTkEntry(stage_row, width=70, justify="center")
            entry.grid(row=0, column=3, padx=10, pady=8)
            entry.bind("<FocusOut>", lambda ev, idx=i: self._on_dpi_entry_change(idx))

            self.dpi_widgets.append({
                "radio": r_btn,
                "slider": slider,
                "entry": entry
            })

        # Apply DPI Button
        ctk.CTkButton(
            dpi_frame, text="Apply DPI Settings",
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            height=36, command=self._apply_dpi_settings
        ).pack(fill="x", pady=(15, 0))

        # Right Column: Performance Settings
        perf_frame = ctk.CTkFrame(tab, fg_color="transparent")
        perf_frame.grid(row=0, column=1, padx=15, pady=15, sticky="nsew")

        ctk.CTkLabel(
            perf_frame, text="Performance & Tuning",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=COLOR_TEXT_MAIN
        ).pack(anchor="w", pady=(0, 15))

        # Report Rate
        ctk.CTkLabel(perf_frame, text="USB Polling Rate", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(5, 5))
        self.segment_rate = ctk.CTkSegmentedButton(
            perf_frame, values=["125 Hz", "250 Hz", "500 Hz", "1000 Hz"],
            selected_color=COLOR_ACCENT, selected_hover_color=COLOR_ACCENT_HOVER,
            command=self._on_report_rate_change
        )
        self.segment_rate.pack(fill="x", pady=(0, 15))

        # Key Debounce Time
        ctk.CTkLabel(perf_frame, text="Button Debounce Delay (Key Response)", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(5, 5))
        debounce_row = ctk.CTkFrame(perf_frame, fg_color="transparent")
        debounce_row.pack(fill="x", pady=(0, 15))

        self.slider_debounce = ctk.CTkSlider(
            debounce_row, from_=1, to=30, number_of_steps=29,
            button_color=COLOR_ACCENT, command=self._on_debounce_slider
        )
        self.slider_debounce.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.lbl_debounce_val = ctk.CTkLabel(debounce_row, text="8 ms", width=50, font=ctk.CTkFont(weight="bold"))
        self.lbl_debounce_val.pack(side="right")

        # Auto-Sleep Timeout
        ctk.CTkLabel(perf_frame, text="Auto-Sleep Timeout", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(5, 5))
        sleep_row = ctk.CTkFrame(perf_frame, fg_color="transparent")
        sleep_row.pack(fill="x", pady=(0, 15))

        self.slider_sleep = ctk.CTkSlider(
            sleep_row, from_=0, to=30, number_of_steps=30,
            button_color=COLOR_ACCENT, command=self._on_sleep_slider
        )
        self.slider_sleep.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.lbl_sleep_val = ctk.CTkLabel(sleep_row, text="10 min", width=60, font=ctk.CTkFont(weight="bold"))
        self.lbl_sleep_val.pack(side="right")

        # Roller Direction Setting Card
        roller_card = ctk.CTkFrame(perf_frame, fg_color=COLOR_BG_DARK, corner_radius=10)
        roller_card.pack(fill="x", pady=(10, 10))

        ctk.CTkLabel(
            roller_card, text="Roller direction setting",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_TEXT_MAIN
        ).pack(anchor="w", padx=15, pady=(10, 2))

        ctk.CTkLabel(
            roller_card, text="Switch the functions of mouse wheel up and mouse wheel down",
            font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=15, pady=(0, 8))

        roller_radio_row = ctk.CTkFrame(roller_card, fg_color="transparent")
        roller_radio_row.pack(anchor="w", padx=15, pady=(0, 12))

        self.scroll_dir_var = ctk.IntVar(value=0)

        ctk.CTkRadioButton(
            roller_radio_row, text="Forward",
            variable=self.scroll_dir_var, value=0,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_ACCENT,
            command=self._on_scroll_direction_changed
        ).pack(side="left", padx=(0, 25))

        ctk.CTkRadioButton(
            roller_radio_row, text="Reverse",
            variable=self.scroll_dir_var, value=1,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_ACCENT,
            command=self._on_scroll_direction_changed
        ).pack(side="left")

    # ─── TAB 2: BUTTON MAPPING ────────────────────────────────────────────────────

    def _build_tab_buttons(self):
        tab = self.tab_buttons
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tab, text="Programmable Mouse Buttons",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=COLOR_TEXT_MAIN
        ).pack(anchor="w", padx=20, pady=(15, 10))

        self.btn_combo_widgets = []
        preset_names = [name.replace("_", " ").title() for name in BUTTON_PRESETS.keys()]

        container = ctk.CTkFrame(tab, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=5)

        for i in range(6):
            row_frame = ctk.CTkFrame(container, fg_color=COLOR_BG_DARK, corner_radius=8)
            row_frame.pack(fill="x", pady=6)
            row_frame.grid_columnconfigure(1, weight=1)

            lbl = BUTTON_LABELS[i] if i < len(BUTTON_LABELS) else f"Button {i+1}"
            ctk.CTkLabel(
                row_frame, text=f"{i+1}.  {lbl}",
                font=ctk.CTkFont(size=14, weight="bold"), width=160, anchor="w"
            ).grid(row=0, column=0, padx=15, pady=10)

            combo = ctk.CTkComboBox(
                row_frame, values=preset_names,
                button_color=COLOR_ACCENT, button_hover_color=COLOR_ACCENT_HOVER,
                dropdown_fg_color=COLOR_CARD_BG
            )
            combo.grid(row=0, column=1, padx=15, pady=10, sticky="ew")

            self.btn_combo_widgets.append(combo)

        # Action Buttons Row
        action_row = ctk.CTkFrame(tab, fg_color="transparent")
        action_row.pack(fill="x", padx=20, pady=15)

        ctk.CTkButton(
            action_row, text="Save Button Mapping",
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            height=38, width=200, command=self._apply_button_mapping
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            action_row, text="Reset to Factory Defaults",
            fg_color="#333645", hover_color="#44485C", text_color=COLOR_TEXT_MAIN,
            height=38, width=200, command=self._reset_buttons_to_default
        ).pack(side="left")

    # ─── TAB 3: RGB LIGHTING ──────────────────────────────────────────────────────

    def _build_tab_rgb(self):
        tab = self.tab_rgb
        tab.grid_columnconfigure(0, weight=1)

        header_card = ctk.CTkFrame(tab, fg_color=COLOR_BG_DARK, corner_radius=10)
        header_card.pack(fill="x", padx=20, pady=(15, 10))

        ctk.CTkLabel(
            header_card, text="light setting",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=COLOR_TEXT_MAIN
        ).pack(anchor="w", padx=15, pady=(12, 2))

        ctk.CTkLabel(
            header_card, text="change the light effect of the mouse",
            font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=15, pady=(0, 12))

        self.light_modes_list = [
            (0, "Wave"),
            (1, "Neon"),
            (2, "Touring Flash"),
            (3, "YOYO Ball"),
            (4, "Unidirectional Flashing"),
            (5, "Circular Breathing"),
            (6, "Turn Off The Light"),
        ]


        mode_names = [m[1] for m in self.light_modes_list]

        dropdown_row = ctk.CTkFrame(tab, fg_color="transparent")
        dropdown_row.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            dropdown_row, text="Select Effect:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=(0, 15))

        self.combo_light_mode = ctk.CTkOptionMenu(
            dropdown_row, values=mode_names,
            button_color=COLOR_ACCENT, button_hover_color=COLOR_ACCENT_HOVER,
            dropdown_fg_color=COLOR_CARD_BG, width=260,
            command=self._on_light_combo_changed
        )
        self.combo_light_mode.pack(side="left")

        # Grid Cards Frame
        scroll_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)
        scroll_frame.grid_columnconfigure((0, 1), weight=1)

        self.rgb_radio_var = ctk.IntVar(value=0)

        for idx, (mode_id, name) in enumerate(self.light_modes_list):
            r_idx = idx // 2
            c_idx = idx % 2

            card = ctk.CTkFrame(scroll_frame, fg_color=COLOR_BG_DARK, corner_radius=8)
            card.grid(row=r_idx, column=c_idx, padx=6, pady=6, sticky="nsew")

            rb = ctk.CTkRadioButton(
                card, text=f"{name}",
                variable=self.rgb_radio_var, value=mode_id,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=COLOR_ACCENT,
                command=lambda m=mode_id: self._on_light_mode_selected(m)
            )
            rb.pack(anchor="w", padx=12, pady=10)

        # Static Color Hardware Note Card
        static_card = ctk.CTkFrame(tab, fg_color=COLOR_BG_DARK, corner_radius=10)
        static_card.pack(fill="x", padx=20, pady=(10, 15))

        ctk.CTkLabel(
            static_card, text="ℹ Static Color Control Note",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_TEXT_MAIN
        ).pack(anchor="w", padx=15, pady=(10, 2))

        ctk.CTkLabel(
            static_card,
            text="On Onikuma CW935 hardware, static solid LED colors (Red, Green, Blue, Yellow, Cyan, Purple) correspond to DPI Stages 1 to 6.\nSelect the active DPI stage on Tab 1 for your preferred static LED color.",
            font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED, justify="left"
        ).pack(anchor="w", padx=15, pady=(0, 10))



    # ─── TAB 4: DEVICE INFO & RESET ───────────────────────────────────────────────

    def _build_tab_info(self):
        tab = self.tab_info
        tab.grid_columnconfigure(0, weight=1)

        info_card = ctk.CTkFrame(tab, fg_color=COLOR_BG_DARK, corner_radius=10)
        info_card.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            info_card, text="Hardware Diagnostics & Details",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=COLOR_TEXT_MAIN
        ).pack(anchor="w", padx=20, pady=(15, 10))

        self.lbl_info_details = ctk.CTkLabel(
            info_card, text="Scanning for device...",
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color=COLOR_TEXT_MUTED, justify="left"
        )
        self.lbl_info_details.pack(anchor="w", padx=20, pady=(0, 15))

        reset_card = ctk.CTkFrame(tab, fg_color=COLOR_BG_DARK, corner_radius=10)
        reset_card.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkLabel(
            reset_card, text="Factory Reset",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=COLOR_ERROR
        ).pack(anchor="w", padx=20, pady=(15, 5))

        ctk.CTkLabel(
            reset_card,
            text="Wipe onboard memory and restore all DPI stages, buttons, lighting, and performance settings to original factory defaults.",
            font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 15))

        ctk.CTkButton(
            reset_card, text="Restore All Factory Defaults",
            fg_color=COLOR_ERROR, hover_color="#D32F2F", text_color="#FFFFFF",
            height=38, command=self._factory_reset
        ).pack(anchor="w", padx=20, pady=(0, 15))

    # ─── MOUSE LOGIC & CONTROLLER CONNECTIVITY ─────────────────────────────────────

    def _try_connect_mouse(self):
        """Attempt to find and connect to Onikuma CW935 mouse."""
        try:
            if not self.mouse:
                self.mouse = OnikumaCW935()
            self.mouse.connect()
            self.mouse.register_callback(self._on_realtime_event)
            self.is_connected = True
            self._update_connection_status_ui(True)
            self._load_config_from_mouse()
        except Exception as e:
            logger.warning(f"Connection failed: {e}")
            self.is_connected = False
            self._update_connection_status_ui(False)

    def _on_realtime_event(self, event_data: dict):
        """Callback executed when an unsolicited push report arrives from hardware."""
        event_type = event_data.get("event")

        if event_type == "dpi_rate_changed":
            dpi_idx = event_data.get("dpi_index", 0)
            rate_idx = event_data.get("report_rate", 3)
            self.after(0, lambda: self._update_realtime_dpi_and_rate(dpi_idx, rate_idx))

        elif event_type == "battery_updated":
            bat = event_data.get("battery")
            if bat:
                bat_text = f"Battery: {bat.percentage}%" + (" ⚡" if bat.charging else "")
                self.after(0, lambda: self.battery_label.configure(text=bat_text))

    def _update_realtime_dpi_and_rate(self, dpi_idx: int, rate_idx: int):
        """Update active DPI radio button and report rate on Tkinter main thread."""
        self.active_dpi_var.set(dpi_idx)
        hz_map = {0: "125 Hz", 1: "250 Hz", 2: "500 Hz", 3: "1000 Hz"}
        if rate_idx in hz_map:
            self.segment_rate.set(hz_map[rate_idx])


    def _update_connection_status_ui(self, connected: bool):
        """Update header connection badge & labels."""
        if connected and self.mouse:
            info = self.mouse.get_info()
            self.status_indicator.configure(
                text=f"● Connected ({info.connection_mode})",
                text_color=COLOR_SUCCESS
            )
            details = (
                f"Model Name:        Onikuma CW935\n"
                f"Sensor:            Instant S203 (12,800 DPI max)\n"
                f"Firmware Version:  {info.firmware_version}\n"
                f"Vendor ID (VID):   0x{info.vendor_id:04X}\n"
                f"Product ID (PID):  0x{info.product_id:04X}\n"
                f"Interface Mode:    {info.connection_mode}"
            )
            self.lbl_info_details.configure(text=details)
        else:
            self.status_indicator.configure(
                text="● Disconnected",
                text_color=COLOR_ERROR
            )
            self.battery_label.configure(text="Battery: --%")
            self.lbl_info_details.configure(text="No mouse detected. Ensure USB cable or 2.4G receiver is plugged in.")

    def _load_config_from_mouse(self):
        """Fetch settings from mouse hardware and populate UI controls."""
        if not self.is_connected or not self.mouse:
            return

        try:
            self.current_config = self.mouse.get_config()
            self.current_buttons = self.mouse.get_buttons()

            cfg = self.current_config

            # Populate DPI
            self.active_dpi_var.set(cfg.dpi_index)
            for i in range(6):
                val = cfg.dpi_values[i] if i < len(cfg.dpi_values) else 800
                self.dpi_widgets[i]["slider"].set(val)
                self.dpi_widgets[i]["entry"].delete(0, "end")
                self.dpi_widgets[i]["entry"].insert(0, str(val))

            # Performance
            hz_str = f"{cfg.report_rate_hz} Hz"
            if hz_str in ["125 Hz", "250 Hz", "500 Hz", "1000 Hz"]:
                self.segment_rate.set(hz_str)

            self.slider_debounce.set(cfg.key_respond)
            self.lbl_debounce_val.configure(text=f"{cfg.key_respond} ms")

            self.slider_sleep.set(cfg.sleep_time)
            self.lbl_sleep_val.configure(text=f"{cfg.sleep_time} min" if cfg.sleep_time else "Off")

            # Buttons
            preset_keys = list(BUTTON_PRESETS.keys())
            for i, btn in enumerate(self.current_buttons[:6]):
                # Find matching preset
                matching_preset = "disabled"
                for p_key, (p_type, p_c1, p_c2, p_c3) in BUTTON_PRESETS.items():
                    if btn.type == p_type and btn.code1 == p_c1 and btn.code2 == p_c2:
                        matching_preset = p_key
                        break
                preset_display = matching_preset.replace("_", " ").title()
                self.btn_combo_widgets[i].set(preset_display)

            # Roller Direction
            self.scroll_dir_var.set(cfg.scroll_flag)

            # RGB Light Mode
            mode_id = cfg.light_mode
            self.rgb_radio_var.set(mode_id)

            # Update OptionMenu dropdown text
            for m_id, name in self.light_modes_list:
                if m_id == mode_id:
                    self.combo_light_mode.set(name)
                    break

            # Battery
            bat = self.mouse.get_battery(force_refresh=True)
            bat_text = f"Battery: {bat.percentage}%" + (" ⚡" if bat.charging else "")
            self.battery_label.configure(text=bat_text)


        except Exception as e:
            logger.error(f"Error loading mouse configuration: {e}")

    # ─── HANDLERS ──────────────────────────────────────────────────────────────────

    def _on_active_dpi_radio_change(self):
        if self.is_connected and self.mouse:
            active_idx = self.active_dpi_var.get()
            self.mouse.set_active_dpi_stage(active_idx)

    def _on_scroll_direction_changed(self):
        if self.is_connected and self.mouse:
            dir_val = self.scroll_dir_var.get()
            self.mouse.set_scroll_direction(dir_val)

    def _on_dpi_slider_change(self, idx: int, val: float):
        dpi_val = int(val)
        self.dpi_widgets[idx]["entry"].delete(0, "end")
        self.dpi_widgets[idx]["entry"].insert(0, str(dpi_val))

    def _on_dpi_entry_change(self, idx: int):
        try:
            val = int(self.dpi_widgets[idx]["entry"].get())
            val = max(DPI_MIN, min(DPI_MAX, val))
            self.dpi_widgets[idx]["slider"].set(val)
        except ValueError:
            pass

    def _apply_dpi_settings(self):
        if not self.is_connected or not self.mouse:
            messagebox.showwarning("Warning", "Mouse not connected.")
            return

        stages = []
        for widget in self.dpi_widgets:
            try:
                v = int(widget["entry"].get())
                stages.append(max(DPI_MIN, min(DPI_MAX, v)))
            except ValueError:
                stages.append(800)

        active_idx = self.active_dpi_var.get()
        self.mouse.set_dpi_stages(stages, active_index=active_idx)
        messagebox.showinfo("Success", "DPI settings saved to mouse onboard memory!")

    def _on_report_rate_change(self, val_str: str):
        if not self.is_connected or not self.mouse:
            return
        hz = int(val_str.replace(" Hz", ""))
        self.mouse.set_report_rate(hz)

    def _on_debounce_slider(self, val: float):
        ms = int(val)
        self.lbl_debounce_val.configure(text=f"{ms} ms")
        if self.is_connected and self.mouse:
            self.mouse.set_debounce(ms)

    def _on_sleep_slider(self, val: float):
        mins = int(val)
        self.lbl_sleep_val.configure(text=f"{mins} min" if mins else "Off")
        if self.is_connected and self.mouse:
            self.mouse.set_sleep_timer(mins)

    def _apply_button_mapping(self):
        if not self.is_connected or not self.mouse:
            messagebox.showwarning("Warning", "Mouse not connected.")
            return

        preset_keys = list(BUTTON_PRESETS.keys())
        for i, combo in enumerate(self.btn_combo_widgets[:6]):
            display_val = combo.get().lower().replace(" ", "_")
            if display_val in BUTTON_PRESETS:
                self.mouse.set_button_preset(i, display_val)

        messagebox.showinfo("Success", "Button mapping saved to mouse onboard memory!")

    def _reset_buttons_to_default(self):
        if not self.is_connected or not self.mouse:
            return
        self.mouse.reset_buttons()
        self._load_config_from_mouse()
        messagebox.showinfo("Success", "Buttons restored to default!")

    def _on_light_combo_changed(self, mode_name: str):
        for mode_id, name in self.light_modes_list:
            if name == mode_name:
                self.rgb_radio_var.set(mode_id)
                self._on_light_mode_selected(mode_id)
                break

    def _on_light_mode_selected(self, mode_id: int):
        for m_id, name in self.light_modes_list:
            if m_id == mode_id:
                self.combo_light_mode.set(name)
                break
        if self.is_connected and self.mouse:
            self.mouse.set_light_mode(mode_id)


    def _factory_reset(self):
        if not self.is_connected or not self.mouse:
            messagebox.showwarning("Warning", "Mouse not connected.")
            return

        if messagebox.askyesno("Confirm Reset", "Are you sure you want to restore ALL factory defaults?"):
            self.mouse.factory_reset()
            self._load_config_from_mouse()
            messagebox.showinfo("Success", "All mouse settings restored to factory defaults!")

    # ─── BACKGROUND THREAD ─────────────────────────────────────────────────────────

    def _background_poll_loop(self):
        """Poll HID push events at 50Hz (20ms interval) for real-time responsiveness."""
        tick_counter = 0
        while self._polling_active:
            time.sleep(0.02)  # 20ms = 50Hz real-time polling
            tick_counter += 1

            if self.is_connected and self.mouse:
                try:
                    # Read any pending HID input reports (triggers _on_realtime_event on hardware push)
                    self.mouse.poll_events()
                except Exception as e:
                    logger.debug(f"Error in background poll: {e}")
            elif not self.is_connected:
                # Auto-retry device discovery every ~2 seconds (100 ticks)
                if tick_counter >= 100:
                    tick_counter = 0
                    devs = find_devices()
                    if devs:
                        self.after(0, self._try_connect_mouse)



    def on_closing(self):
        self._polling_active = False
        if self.mouse:
            self.mouse.disconnect()
        self.destroy()


def main():
    app = OnikumaGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
