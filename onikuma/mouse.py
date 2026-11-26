"""
Onikuma CW935 High-Level Mouse Controller API
==============================================
Provides intuitive Python interface for all features:
- DPI stages and active DPI control
- Button programming and preset mapping
- Lighting effect control
- Report rate, LOD, Debounce, Sleep timer
- Battery status & Device information
"""

import time
import logging
from typing import Optional, List, Dict, Tuple


from .device import HIDDevice, find_devices
from .protocol import (
    ButtonAssignment, MouseConfig, BatteryInfo, DeviceInfo,
    ReportRate, ButtonType, MouseButton, MouseFunc, LightMode,
    BUTTON_PRESETS, DEFAULT_BUTTONS, DEFAULT_CONFIG, CONNECTION_MODES,
    DPI_MIN, DPI_MAX, DPI_STEP,
    cmd_get_version, cmd_get_battery, cmd_get_config, cmd_set_config,
    cmd_get_buttons, cmd_set_buttons, cmd_set_light_mode, cmd_get_connection_status,
    cmd_reset_buttons,
    parse_version, parse_battery, parse_config, parse_buttons, parse_connection_status,
    validate_response, CMD_GET_VERSION, CMD_GET_BATTERY, CMD_GET_CONFIG, CMD_GET_BUTTONS,
    CMD_GET_STATUS
)

logger = logging.getLogger(__name__)


class OnikumaCW935:
    """
    High-level controller for Onikuma CW935 gaming mouse.
    """
    def __init__(self, device: Optional[HIDDevice] = None):
        self.device = device or self._auto_detect()
        self._last_battery_pct: int = 0
        self._last_charging: bool = False

    @staticmethod
    def _auto_detect() -> HIDDevice:
        """Find and return the first matching Onikuma mouse HID interface."""
        devices = find_devices()
        if not devices:
            raise RuntimeError("No Onikuma CW935 mouse found! Ensure it is connected via USB or 2.4G receiver.")

        # Prefer interface with vendor usage page 0xFF01 / usage 0x10 if available, else first device
        target_dev = devices[0]
        for d in devices:
            if d.get('usage_page') == 0xFF01 and d.get('usage') == 0x10:
                target_dev = d
                break

        return HIDDevice(
            path=target_dev.get('path'),
            vendor_id=target_dev.get('vendor_id', 0),
            product_id=target_dev.get('product_id', 0),
            product_string=str(target_dev.get('product_string', ''))
        )

    def connect(self) -> bool:
        """Open HID device connection."""
        return self.device.open()

    def register_callback(self, callback):
        """Register a callback for real-time push events (e.g. DPI button presses)."""
        self.device.register_callback(callback)

    def unregister_callback(self, callback):
        """Unregister a real-time push event callback."""
        self.device.unregister_callback(callback)

    def poll_events(self):
        """Read any pending HID reports and dispatch events."""
        self.device.read_single()

    def disconnect(self):
        """Close HID device connection."""
        self.device.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    # ─── Device & Battery Information ──────────────────────────────────────────────

    def get_info(self) -> DeviceInfo:
        """Get firmware version and connection details."""
        resp = self.device.send_command(cmd_get_version(), expected_cmd=CMD_GET_VERSION)
        fw_ver = parse_version(resp) if resp else "Unknown"

        vid = self.device.vendor_id
        prod_str = self.device.product_string.upper()

        if vid == 43172 or "USB" in prod_str:
            conn_mode = "Wired USB"
        elif vid == 43173 or "2.4G" in prod_str:
            conn_mode = "2.4G Wireless Dongle"
        else:
            conn_mode = CONNECTION_MODES.get(vid, "2.4G Wireless Dongle")

        return DeviceInfo(
            firmware_version=fw_ver,
            vendor_id=self.device.vendor_id,
            product_id=self.device.product_id,
            connection_mode=conn_mode
        )

    def get_battery(self, force_refresh: bool = False) -> BatteryInfo:
        """Get battery percentage and charging state matching vendor UI mapping."""
        resp = self.device.send_command(cmd_get_battery(), expected_cmd=CMD_GET_BATTERY)
        if not resp:
            if self._last_battery_pct > 0:
                return BatteryInfo(percentage=self._last_battery_pct, charging=self._last_charging)
            return BatteryInfo()

        raw_info = parse_battery(resp)
        if raw_info.percentage <= 0:
            if self._last_battery_pct > 0:
                return BatteryInfo(percentage=self._last_battery_pct, charging=self._last_charging)
            return raw_info

        mapped_pct = raw_info.percentage

        if force_refresh or self._last_battery_pct == 0 or raw_info.charging:
            self._last_battery_pct = mapped_pct
            self._last_charging = raw_info.charging
        else:
            # Retain stable reading unless mapped battery level changes by a step
            if abs(mapped_pct - self._last_battery_pct) >= 10:
                self._last_battery_pct = mapped_pct
                self._last_charging = raw_info.charging

        return BatteryInfo(percentage=self._last_battery_pct, charging=self._last_charging)




    def get_connection_status(self) -> int:
        """Get raw connection status code."""
        resp = self.device.send_command(cmd_get_connection_status(), expected_cmd=CMD_GET_STATUS)
        return parse_connection_status(resp) if resp else 0

    # ─── Configuration & DPI ──────────────────────────────────────────────────────

    def get_config(self) -> MouseConfig:
        """Fetch full mouse configuration (DPI, report rate, lighting, LOD, sleep, etc.)."""
        resp = self.device.send_command(cmd_get_config(), expected_cmd=CMD_GET_CONFIG)
        if resp:
            return parse_config(resp)
        logger.warning("Failed to fetch mouse config, returning default.")
        return DEFAULT_CONFIG

    def save_config(self, config: MouseConfig) -> bool:
        """Write configuration to mouse hardware memory."""
        cmd = cmd_set_config(config)
        self.device.write(cmd)
        return True

    def set_dpi_stages(self, stages: List[int], active_index: int = 0) -> MouseConfig:
        """
        Configure DPI stages.
        :param stages: List of 1 to 6 DPI values (between 50 and 12800)
        :param active_index: 0-based index of the currently active DPI stage
        """
        config = self.get_config()

        # Sanitize DPI values
        clean_stages = []
        for v in stages[:6]:
            val = max(DPI_MIN, min(DPI_MAX, int(v)))
            clean_stages.append(val)

        # Pad with last stage or default if less than 6
        while len(clean_stages) < 6:
            clean_stages.append(clean_stages[-1] if clean_stages else 800)

        config.dpi_count = len(stages[:6])
        config.dpi_values = clean_stages
        config.dpi_index = max(0, min(config.dpi_count - 1, active_index))

        self.save_config(config)
        return config

    def set_active_dpi_stage(self, stage_index: int) -> MouseConfig:
        """Switch current active DPI stage (0-based)."""
        config = self.get_config()
        config.dpi_index = max(0, min(config.dpi_count - 1, stage_index))
        self.save_config(config)
        return config

    def set_quick_dpi(self, dpi: int) -> MouseConfig:
        """Set active stage (index 0) to specific DPI immediately."""
        config = self.get_config()
        dpi_val = max(DPI_MIN, min(DPI_MAX, int(dpi)))
        config.dpi_values[config.dpi_index] = dpi_val
        self.save_config(config)
        return config

    # ─── Report Rate & Performance ─────────────────────────────────────────────────

    def set_report_rate(self, hz: int) -> MouseConfig:
        """
        Set polling rate in Hz (125, 250, 500, 1000).
        """
        config = self.get_config()
        rate_enum = ReportRate.from_hz(hz)
        config.report_rate = rate_enum.value
        self.save_config(config)
        return config

    def set_lod(self, level: int) -> MouseConfig:
        """
        Set Lift-Off Distance level (1 = low, 2 = high).
        """
        config = self.get_config()
        config.lod_value = max(1, min(2, level))
        self.save_config(config)
        return config

    def set_debounce(self, ms: int) -> MouseConfig:
        """
        Set key response debounce time in ms (e.g. 2, 4, 8, 12, 16).
        """
        config = self.get_config()
        config.key_respond = max(1, min(30, ms))
        self.save_config(config)
        return config

    def set_sleep_timer(self, minutes: int) -> MouseConfig:
        """
        Set auto-sleep timeout in minutes (0 = off, 1-30 minutes).
        """
        config = self.get_config()
        config.sleep_time = max(0, min(30, int(minutes)))
        self.save_config(config)
        return config

    def set_scroll_direction(self, direction: int) -> MouseConfig:
        """
        Set mouse wheel scroll direction (0 = Forward / Normal, 1 = Reverse / Inverted).
        """
        config = self.get_config()
        config.scroll_flag = 1 if direction else 0
        self.save_config(config)
        return config

    # ─── Lighting Control ─────────────────────────────────────────────────────────

    def set_light_mode(self, mode: int) -> MouseConfig:
        """
        Set mouse RGB lighting effect mode (0 = Wave, 1 = Neon, 2 = Touring Flash,
        3 = YOYO Ball, 4 = Unidirectional Flashing, 5 = Circular Breathing,
        6 = Turn Off The Light, 7-13 = Static colors).
        """
        mode_val = mode & 0xFF
        config = self.get_config()
        config.light_mode = mode_val

        # Send live light command (CMD 0x21 with byte[3]=1)
        self.device.write(cmd_set_light_mode(mode_val))

        # Short delay to allow MCU hardware to process light change
        time.sleep(0.035)

        # Save config with updated light_mode to EEPROM (CMD 0x0F)
        self.save_config(config)
        return config




    # ─── Button Remapping ─────────────────────────────────────────────────────────

    def get_buttons(self) -> List[ButtonAssignment]:
        """Fetch current button assignments for all 6 buttons."""
        resp = self.device.send_command(cmd_get_buttons(), expected_cmd=CMD_GET_BUTTONS)
        if resp:
            return parse_buttons(resp)
        return list(DEFAULT_BUTTONS)

    def set_button(self, index: int, btn_type: int, code1: int, code2: int = 0, code3: int = 0, name: str = "") -> List[ButtonAssignment]:
        """
        Program a specific button (0-5).
        """
        buttons = self.get_buttons()
        if 0 <= index < len(buttons):
            buttons[index] = ButtonAssignment(
                index=index,
                type=btn_type,
                code1=code1,
                code2=code2,
                code3=code3,
                name=name
            )
            self.device.write(cmd_set_buttons(buttons))
        return buttons

    def set_button_preset(self, index: int, preset_name: str) -> List[ButtonAssignment]:
        """
        Assign a preset to a button.
        Preset names: left_click, right_click, middle_click, back, forward,
                      dpi_cycle, dpi_minus, scroll_up, scroll_down, fire_key,
                      volume_up, volume_down, mute, play_pause, next_track, prev_track,
                      calculator, my_computer, homepage, disabled
        """
        if preset_name not in BUTTON_PRESETS:
            raise ValueError(f"Unknown preset '{preset_name}'. Valid presets: {list(BUTTON_PRESETS.keys())}")

        btn_type, code1, code2, code3 = BUTTON_PRESETS[preset_name]
        return self.set_button(index, btn_type, code1, code2, code3, name=preset_name.replace("_", " ").title())

    def reset_buttons(self) -> List[ButtonAssignment]:
        """Reset all button assignments to factory defaults."""
        self.device.write(cmd_reset_buttons())
        return list(DEFAULT_BUTTONS)

    def factory_reset(self) -> Tuple[MouseConfig, List[ButtonAssignment]]:
        """Restore all mouse settings and buttons to factory defaults."""
        config = DEFAULT_CONFIG
        self.save_config(config)
        buttons = self.reset_buttons()
        return config, buttons
