"""
Onikuma CW935 HID Protocol
===========================
All command builders, response parsers, and protocol constants.
Reverse-engineered from vendor web software (DM01/DM07/DM09).

Protocol overview:
  - 64-byte HID output reports, report ID = 0
  - Command magic: 0x55
  - Response magic: 0xAA (first byte of input report)
  - All multi-byte values are little-endian uint16
"""

from enum import IntEnum
from dataclasses import dataclass, field
from typing import Optional

# ─── Device Identification ─────────────────────────────────────────────────────

# Vendor IDs
VID_WIRED = 43172        # 0xA8A4 — Wired USB connection
VID_WIRELESS = 43173     # 0xA8A5 — 2.4G wireless dongle
VID_KEYBOARD = 43174     # 0xA8A6 — Keyboard (not used)
VID_ALT = 14391          # 0x3837 — Alternative VID (G3 V2 model)

# Product IDs
PID_CW935 = 8789         # 0x2255 — CW935 / DM01

# HID Usage Page and Usage for the vendor-defined config interface
USAGE_PAGE = 0xFF01      # 65281 — Vendor defined
USAGE = 0x10             # 16

# All known VID/PID combos for CW935
KNOWN_DEVICES = [
    (VID_WIRED, PID_CW935),
    (VID_WIRELESS, PID_CW935),
]

# Connection mode lookup
CONNECTION_MODES = {
    VID_WIRED: "Wired USB",
    VID_WIRELESS: "2.4G Wireless",
    VID_ALT: "2.4G Wireless",
}


# ─── Protocol Constants ────────────────────────────────────────────────────────

REPORT_ID = 0x00
CMD_MAGIC = 0x55         # Command send marker
RSP_MAGIC = 0xAA         # Response marker
PACKET_SIZE = 64         # Payload size (excluding report ID)
WRITE_SIZE = 65          # Report ID + payload

# Command IDs
CMD_GET_VERSION = 0x03
CMD_GET_DONGLE_VERSION = 0x04
CMD_GET_BUTTONS = 0x08
CMD_SET_BUTTONS = 0x09
CMD_WRITE_MACRO = 0x0D
CMD_GET_CONFIG = 0x0E
CMD_SET_CONFIG = 0x0F
CMD_SAVE_MACRO = 0x10
CMD_SET_LIGHT = 0x21
CMD_GET_BATTERY = 0x30
CMD_GET_DEVICE_ID = 0x52
CMD_GET_STATUS = 0xED
CMD_PUSH_DPI_STATUS = 0xFA    # 250 — Unsolicited push report when DPI button or report rate changes

# ─── Sensor Limits (Instant S203) ──────────────────────────────────────────────

DPI_MIN = 50
DPI_MAX = 12800
DPI_STEP = 50
DPI_STAGES_MAX = 6

# ─── Enums ──────────────────────────────────────────────────────────────────────

class ReportRate(IntEnum):
    """Polling rate in Hz. Wire value = index + 1."""
    HZ_125 = 0
    HZ_250 = 1
    HZ_500 = 2
    HZ_1000 = 3

    @property
    def hz(self) -> int:
        return [125, 250, 500, 1000][self.value]

    @property
    def wire_value(self) -> int:
        return self.value + 1

    @classmethod
    def from_wire(cls, wire_val: int) -> "ReportRate":
        return cls(max(0, min(3, wire_val - 1)))

    @classmethod
    def from_hz(cls, hz: int) -> "ReportRate":
        hz_map = {125: 0, 250: 1, 500: 2, 1000: 3}
        return cls(hz_map.get(hz, 3))


class ButtonType(IntEnum):
    """Button assignment type codes."""
    DISABLED = 0x00
    KEYBOARD = 0x10       # Keyboard key (code1=modifier mask, code2=keycode)
    MOUSE_BUTTON = 0x20   # Mouse button (code1=button bitmask)
    MOUSE_FUNC = 0x21     # Mouse function (DPI cycle, scroll, etc.)
    MEDIA_KEY = 0x30      # Media/consumer key
    MACRO = 0x70          # Macro assignment (code1=macro index)


class MouseButton(IntEnum):
    """Mouse button bitmask values (for ButtonType.MOUSE_BUTTON code1)."""
    DISABLED = 0x00
    LEFT_CLICK = 0x01
    RIGHT_CLICK = 0x02
    MIDDLE_CLICK = 0x04
    BACK = 0x08
    FORWARD = 0x10


class MouseFunc(IntEnum):
    """Mouse function code1 values (for ButtonType.MOUSE_FUNC)."""
    DPI_CYCLE_UP = 0x55     # code2=0
    SCROLL_UP = 0x38        # code2=1
    SCROLL_DOWN = 0x38      # code2=255
    DPI_MINUS = 0xAA        # code2=0
    FIRE_KEY = 0x61         # code2=0


class LightMode(IntEnum):
    """Lighting effect modes supported by Onikuma CW935 firmware (0 to 6)."""
    WAVE = 0
    NEON = 1
    TOURING_FLASH = 2
    YOYO_BALL = 3
    UNIDIRECTIONAL_FLASHING = 4
    CIRCULAR_BREATHING = 5
    OFF = 6


LIGHT_MODE_LABELS = {
    0: "Wave",
    1: "Neon",
    2: "Touring Flash",
    3: "YOYO Ball",
    4: "Unidirectional Flashing",
    5: "Circular Breathing",
    6: "Turn Off The Light",
}

# Static LED color associated with each DPI stage on Onikuma CW935 hardware
DPI_STAGE_COLORS = [
    ("Blue", "#0000FF"),
    ("Green", "#00FF00"),
    ("Yellow", "#FFFF00"),
    ("Cyan", "#00FFFF"),
    ("Magenta", "#FF00FF"),
    ("White", "#FFFFFF"),
]





# ─── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class ButtonAssignment:
    """A single button assignment."""
    index: int
    type: int
    code1: int
    code2: int
    code3: int
    name: str = ""

    @property
    def type_name(self) -> str:
        try:
            return ButtonType(self.type).name
        except ValueError:
            return f"UNKNOWN(0x{self.type:02X})"

    @property
    def description(self) -> str:
        if self.name:
            return self.name
        return self._auto_describe()

    def _auto_describe(self) -> str:
        if self.type == ButtonType.MOUSE_BUTTON:
            try:
                return MouseButton(self.code1).name.replace("_", " ").title()
            except ValueError:
                return f"Mouse 0x{self.code1:02X}"
        elif self.type == ButtonType.MOUSE_FUNC:
            if self.code1 == MouseFunc.DPI_CYCLE_UP:
                return "DPI Cycle +"
            elif self.code1 == MouseFunc.SCROLL_UP and self.code2 == 1:
                return "Scroll Up"
            elif self.code1 == MouseFunc.SCROLL_DOWN and self.code2 == 255:
                return "Scroll Down"
            elif self.code1 == MouseFunc.DPI_MINUS:
                return "DPI -"
            elif self.code1 == MouseFunc.FIRE_KEY:
                return "Fire Key"
            return f"Function 0x{self.code1:02X}"
        elif self.type == ButtonType.KEYBOARD:
            modifiers = _decode_modifiers(self.code1)
            key = KEYCODE_NAMES.get(self.code2, f"Key(0x{self.code2:02X})")
            if modifiers:
                return " + ".join(modifiers) + " + " + key
            return key
        elif self.type == ButtonType.MEDIA_KEY:
            return MEDIA_KEY_NAMES.get((self.code1, self.code2), f"Media(0x{self.code1:02X},0x{self.code2:02X})")
        elif self.type == ButtonType.MACRO:
            return f"Macro {self.code1 + 1}"
        elif self.type == ButtonType.DISABLED or self.type == 0xFF:
            return "Disabled"
        return f"Type(0x{self.type:02X}) [{self.code1},{self.code2},{self.code3}]"


@dataclass
class MouseConfig:
    """Full mouse configuration."""
    light_mode: int = 0
    report_rate: int = 3       # ReportRate index (0-3)
    dpi_count: int = 6
    dpi_index: int = 2         # Active DPI stage (0-based)
    dpi_values: list = field(default_factory=lambda: [800, 1600, 2400, 3200, 5000, 12000])
    scroll_flag: int = 0       # 0=normal, 1=inverted
    lod_value: int = 1         # Lift-off distance (1=low, 2=high)
    sensor_flag: int = 53      # 0x35
    key_respond: int = 8       # Debounce in ms
    sleep_time: int = 10       # Sleep timeout in minutes
    highspeed_mode: int = 0
    wakeup_flag: int = 1
    move_light_flag: int = 1

    @property
    def active_dpi(self) -> int:
        if 0 <= self.dpi_index < len(self.dpi_values):
            return self.dpi_values[self.dpi_index]
        return 0

    @property
    def report_rate_hz(self) -> int:
        return ReportRate(self.report_rate).hz


@dataclass
class BatteryInfo:
    """Battery status."""
    percentage: int = 0
    charging: bool = False


@dataclass
class DeviceInfo:
    """Device identification and firmware info."""
    firmware_version: str = "0.0.0"
    vendor_id: int = 0
    product_id: int = 0
    connection_mode: str = "Unknown"


# ─── Key Code / Media Key Name Tables ──────────────────────────────────────────

KEYCODE_NAMES = {
    4: "A", 5: "B", 6: "C", 7: "D", 8: "E", 9: "F", 10: "G", 11: "H",
    12: "I", 13: "J", 14: "K", 15: "L", 16: "M", 17: "N", 18: "O", 19: "P",
    20: "Q", 21: "R", 22: "S", 23: "T", 24: "U", 25: "V", 26: "W", 27: "X",
    28: "Y", 29: "Z",
    30: "1", 31: "2", 32: "3", 33: "4", 34: "5", 35: "6", 36: "7", 37: "8",
    38: "9", 39: "0",
    40: "Enter", 41: "Esc", 42: "Backspace", 43: "Tab", 44: "Space",
    45: "- _", 46: "= +", 47: "[ {", 48: "] }", 49: "\\ |",
    51: "; :", 52: "' \"", 53: "` ~", 54: ", <", 55: ". >", 56: "/ ?",
    57: "Caps Lock",
    58: "F1", 59: "F2", 60: "F3", 61: "F4", 62: "F5", 63: "F6",
    64: "F7", 65: "F8", 66: "F9", 67: "F10", 68: "F11", 69: "F12",
    70: "Print Scr", 71: "Scroll Lock", 72: "Pause",
    73: "Insert", 74: "Home", 75: "Page Up", 76: "Delete", 77: "End", 78: "Page Down",
    79: "Right", 80: "Left", 81: "Down", 82: "Up",
    83: "Num Lock", 84: "Num /", 85: "Num *", 86: "Num -", 87: "Num +",
    88: "Num Enter",
    89: "Num 1", 90: "Num 2", 91: "Num 3", 92: "Num 4", 93: "Num 5",
    94: "Num 6", 95: "Num 7", 96: "Num 8", 97: "Num 9", 98: "Num 0",
    99: "Num .",
    101: "Menu", 117: "Help",
    224: "L-Ctrl", 225: "L-Shift", 226: "L-Alt", 227: "L-Win",
    228: "R-Ctrl", 229: "R-Shift", 230: "R-Alt", 231: "R-Win",
}

MEDIA_KEY_NAMES = {
    (233, 0): "Volume Up", (234, 0): "Volume Down", (226, 0): "Mute",
    (205, 0): "Play/Pause", (183, 0): "Stop",
    (182, 0): "Prev Track", (181, 0): "Next Track",
    (131, 1): "Multimedia", (35, 2): "Homepage",
    (39, 2): "Web Refresh", (38, 2): "Web Stop",
    (37, 2): "Web Forward", (36, 2): "Web Back",
    (42, 2): "Web Favorites", (33, 2): "Web Search",
    (146, 1): "Calculator", (148, 1): "My Computer",
    (138, 1): "Mail",
}

# Default button labels (physical positions)
BUTTON_LABELS = [
    "Left Click",      # Button 0
    "Right Click",     # Button 1
    "Middle Click",    # Button 2
    "Back (Side)",     # Button 3
    "Forward (Side)",  # Button 4
    "DPI Button",      # Button 5
]

# Default button assignments (factory defaults)
DEFAULT_BUTTONS = [
    ButtonAssignment(0, 0x20, 0x01, 0, 0, "Left Click"),
    ButtonAssignment(1, 0x20, 0x02, 0, 0, "Right Click"),
    ButtonAssignment(2, 0x20, 0x04, 0, 0, "Middle Click"),
    ButtonAssignment(3, 0x20, 0x08, 0, 0, "Back"),
    ButtonAssignment(4, 0x20, 0x10, 0, 0, "Forward"),
    ButtonAssignment(5, 0x21, 0x55, 0, 0, "DPI Cycle +"),
]

# Default DPI config
DEFAULT_CONFIG = MouseConfig(
    light_mode=0,
    report_rate=3,
    dpi_count=6,
    dpi_index=2,
    dpi_values=[800, 1600, 2400, 3200, 5000, 12000],
    scroll_flag=0,
    lod_value=1,
    sensor_flag=53,
    key_respond=8,
    sleep_time=10,
    highspeed_mode=0,
    wakeup_flag=1,
    move_light_flag=1,
)

# ─── Button Presets ─────────────────────────────────────────────────────────────

# Easy-to-use presets for button assignment
BUTTON_PRESETS = {
    "left_click":    (ButtonType.MOUSE_BUTTON, MouseButton.LEFT_CLICK, 0, 0),
    "right_click":   (ButtonType.MOUSE_BUTTON, MouseButton.RIGHT_CLICK, 0, 0),
    "middle_click":  (ButtonType.MOUSE_BUTTON, MouseButton.MIDDLE_CLICK, 0, 0),
    "back":          (ButtonType.MOUSE_BUTTON, MouseButton.BACK, 0, 0),
    "forward":       (ButtonType.MOUSE_BUTTON, MouseButton.FORWARD, 0, 0),
    "dpi_cycle":     (ButtonType.MOUSE_FUNC, MouseFunc.DPI_CYCLE_UP, 0, 0),
    "dpi_minus":     (ButtonType.MOUSE_FUNC, MouseFunc.DPI_MINUS, 0, 0),
    "scroll_up":     (ButtonType.MOUSE_FUNC, MouseFunc.SCROLL_UP, 1, 0),
    "scroll_down":   (ButtonType.MOUSE_FUNC, MouseFunc.SCROLL_DOWN, 255, 0),
    "fire_key":      (ButtonType.MOUSE_FUNC, MouseFunc.FIRE_KEY, 0, 0),
    "disabled":      (ButtonType.DISABLED, 0, 0, 0),
    # Media keys
    "volume_up":     (ButtonType.MEDIA_KEY, 233, 0, 0),
    "volume_down":   (ButtonType.MEDIA_KEY, 234, 0, 0),
    "mute":          (ButtonType.MEDIA_KEY, 226, 0, 0),
    "play_pause":    (ButtonType.MEDIA_KEY, 205, 0, 0),
    "next_track":    (ButtonType.MEDIA_KEY, 181, 0, 0),
    "prev_track":    (ButtonType.MEDIA_KEY, 182, 0, 0),
    "calculator":    (ButtonType.MEDIA_KEY, 146, 1, 0),
    "my_computer":   (ButtonType.MEDIA_KEY, 148, 1, 0),
    "homepage":      (ButtonType.MEDIA_KEY, 35, 2, 0),
}


# ─── Helper Functions ───────────────────────────────────────────────────────────

def encode_dpi(value: int) -> tuple[int, int]:
    """Encode DPI value as little-endian uint16 (low_byte, high_byte)."""
    value = max(DPI_MIN, min(DPI_MAX, value))
    return (value & 0xFF, (value >> 8) & 0xFF)


def decode_dpi(low: int, high: int) -> int:
    """Decode little-endian uint16 to DPI value."""
    value = (high << 8) | low
    if value < DPI_MIN or value > 50000:
        return DPI_MIN
    return value


def _decode_modifiers(mask: int) -> list[str]:
    """Decode keyboard modifier bitmask into names."""
    mods = []
    if mask & 0x01 or mask & 0x10:
        mods.append("Ctrl")
    if mask & 0x02 or mask & 0x20:
        mods.append("Shift")
    if mask & 0x04 or mask & 0x40:
        mods.append("Alt")
    if mask & 0x08 or mask & 0x80:
        mods.append("Win")
    return mods


def _make_packet(*args: int) -> bytes:
    """Build a 65-byte write packet (report ID + 64 payload), zero-padded."""
    buf = bytearray(WRITE_SIZE)
    for i, val in enumerate(args):
        if i < WRITE_SIZE:
            buf[i] = val & 0xFF
    return bytes(buf)


# ─── Command Builders ──────────────────────────────────────────────────────────

def cmd_get_version() -> bytes:
    """Build GET VERSION command (CMD 0x03)."""
    return _make_packet(REPORT_ID, CMD_MAGIC, CMD_GET_VERSION)


def cmd_get_battery() -> bytes:
    """Build GET BATTERY command (CMD 0x30). Matches vendor web app spec: [0, 85, 48, 165, 11, 46]."""
    return _make_packet(
        REPORT_ID, CMD_MAGIC, CMD_GET_BATTERY,
        0xA5, 0x0B, 0x2E
    )



def cmd_get_config() -> bytes:
    """Build GET CONFIG command (CMD 0x0E).
    Returns DPI, report rate, light mode, LOD, debounce, sleep settings.
    """
    return _make_packet(
        REPORT_ID, CMD_MAGIC, CMD_GET_CONFIG,
        0xA5, 0x0B, 0x30, 0x01, 0x01, 0x01
    )


def cmd_set_config(config: MouseConfig) -> bytes:
    """Build SET CONFIG command (CMD 0x0F)."""
    buf = bytearray(WRITE_SIZE)
    buf[0] = REPORT_ID
    buf[1] = CMD_MAGIC
    buf[2] = CMD_SET_CONFIG
    buf[3] = 0xAE
    buf[4] = 0x0A
    buf[5] = 0x2F
    buf[6] = 0x01
    buf[7] = 0x01
    buf[8] = 0x01
    buf[9] = 0x00
    buf[10] = config.light_mode & 0xFF
    buf[11] = ReportRate(config.report_rate).wire_value
    buf[12] = config.dpi_count & 0xFF
    buf[13] = (config.dpi_index + 1) & 0xFF

    # Encode up to 6 DPI values as little-endian uint16
    for i in range(6):
        dpi = config.dpi_values[i] if i < len(config.dpi_values) else DPI_MIN
        lo, hi = encode_dpi(dpi)
        buf[14 + i * 2] = lo
        buf[15 + i * 2] = hi

    buf[49] = config.scroll_flag & 0xFF
    buf[50] = config.lod_value & 0xFF
    buf[51] = config.sensor_flag & 0xFF
    buf[52] = config.key_respond & 0xFF
    buf[53] = config.sleep_time & 0xFF
    buf[54] = config.highspeed_mode & 0xFF
    buf[55] = ((config.wakeup_flag & 0x0F) << 4) | (config.move_light_flag & 0x0F)

    return bytes(buf)


def cmd_get_buttons() -> bytes:
    """Build GET BUTTONS command (CMD 0x08)."""
    return _make_packet(
        REPORT_ID, CMD_MAGIC, CMD_GET_BUTTONS,
        0xA5, 0x0B, 0x2C
    )


def cmd_set_buttons(buttons: list[ButtonAssignment]) -> bytes:
    """Build SET BUTTONS command (CMD 0x09)."""
    buf = bytearray(WRITE_SIZE)
    buf[0] = REPORT_ID
    buf[1] = CMD_MAGIC
    buf[2] = CMD_SET_BUTTONS
    buf[3] = 0xA5
    buf[4] = 0x22
    buf[5] = 0x2C

    # Fill default template first (bytes 9-48)
    defaults = [
        (0x20, 0x01, 0x00, 0x00),  # Left click
        (0x20, 0x02, 0x00, 0x00),  # Right click
        (0x20, 0x04, 0x00, 0x00),  # Middle click
        (0x20, 0x08, 0x00, 0x00),  # Back
        (0x20, 0x10, 0x00, 0x00),  # Forward
        (0x21, 0x55, 0x00, 0x00),  # DPI cycle
        (0x21, 0x38, 0x01, 0x00),  # Scroll up
        (0x21, 0x38, 0xFF, 0x00),  # Scroll down
        (0x21, 0xAA, 0x00, 0x00),  # DPI-
        (0x21, 0x61, 0x00, 0x00),  # Fire key
    ]
    for i, (t, c1, c2, c3) in enumerate(defaults):
        off = 9 + i * 4
        buf[off] = t
        buf[off + 1] = c1
        buf[off + 2] = c2
        buf[off + 3] = c3

    # Override with actual button assignments (first 6 buttons)
    for btn in buttons[:6]:
        off = 9 + btn.index * 4
        buf[off] = btn.type & 0xFF
        buf[off + 1] = btn.code1 & 0xFF
        buf[off + 2] = btn.code2 & 0xFF
        buf[off + 3] = btn.code3 & 0xFF

    return bytes(buf)


def cmd_reset_buttons() -> bytes:
    """Build RESET BUTTONS command (CMD 0x09 with factory defaults)."""
    return cmd_set_buttons(DEFAULT_BUTTONS)


def cmd_set_light_mode(mode: int) -> bytes:
    """Build SET LIGHT MODE command (CMD 0x21). Matches vendor JS: [0, 85, 33, 1, 0, 3, ... buf[11]=mode]."""
    buf = bytearray(WRITE_SIZE)
    buf[0] = REPORT_ID
    buf[1] = CMD_MAGIC
    buf[2] = CMD_SET_LIGHT
    buf[3] = 0x01
    buf[4] = 0x00
    buf[5] = 0x03
    buf[11] = mode & 0xFF
    return bytes(buf)



def cmd_get_connection_status() -> bytes:
    """Build GET CONNECTION STATUS command (CMD 0xED)."""
    return _make_packet(
        REPORT_ID, CMD_MAGIC, CMD_GET_STATUS, 0x01
    )


# ─── Response Parsers ──────────────────────────────────────────────────────────

def validate_response(data: bytes, expected_cmd: Optional[int] = None) -> bool:
    """Check if response has valid magic byte and optionally matches expected command."""
    if not data or len(data) < 2:
        return False
    if data[0] != RSP_MAGIC:
        return False
    if expected_cmd is not None and data[1] != expected_cmd:
        return False
    return True


def parse_version(data: bytes) -> str:
    """Parse firmware version from GET VERSION response."""
    parts = []
    for i in [23, 24, 25]:
        if i < len(data) and 48 <= data[i] <= 57:  # ASCII '0'-'9'
            parts.append(chr(data[i]))
        else:
            parts.append("0")
    return ".".join(parts)


def map_vendor_battery_percentage(raw_val: int) -> int:
    """
    Map raw hardware battery byte (0-100) to vendor UI percentage (10-100%).
    Extracted from DM09 vendor JS bundle (iH component range table).
    """
    if raw_val <= 14:
        return 10
    elif raw_val <= 24:
        return 20
    elif raw_val <= 34:
        return 30
    elif raw_val <= 44:
        return 40
    elif raw_val <= 54:
        return 50
    elif raw_val <= 64:
        return 60
    elif raw_val <= 74:
        return 70
    elif raw_val <= 84:
        return 80
    elif raw_val <= 98:
        return 90
    else:
        return 100


def parse_battery(data: bytes) -> BatteryInfo:
    """Parse battery info from GET BATTERY response."""
    if len(data) < 10 or data[0] != RSP_MAGIC or data[1] != CMD_GET_BATTERY:
        return BatteryInfo()
    raw_pct = data[8] & 0xFF
    mapped_pct = map_vendor_battery_percentage(raw_pct)
    return BatteryInfo(
        percentage=mapped_pct,
        charging=bool(data[9])
    )




def parse_config(data: bytes) -> MouseConfig:
    """Parse full mouse config from GET CONFIG response."""
    if len(data) < 56:
        return MouseConfig()

    # Validate response isn't all zeros or all 0xFF
    if all(b == 0 for b in data[13:16]) or all(b == 0xFF for b in data[13:16]):
        return DEFAULT_CONFIG

    dpi_values = []
    for i in range(6):
        lo = data[13 + i * 2]
        hi = data[14 + i * 2]
        dpi_values.append(decode_dpi(lo, hi))

    dpi_index = max(0, data[12] - 1)

    return MouseConfig(
        light_mode=data[9],
        report_rate=max(0, min(3, data[10] - 1)),
        dpi_count=data[11],
        dpi_index=dpi_index,
        dpi_values=dpi_values,
        scroll_flag=data[48] if len(data) > 48 else 0,
        lod_value=data[49] if len(data) > 49 else 1,
        sensor_flag=data[50] if len(data) > 50 else 53,
        key_respond=data[51] if len(data) > 51 else 8,
        sleep_time=data[52] if len(data) > 52 else 10,
        highspeed_mode=data[53] if len(data) > 53 else 0,
        wakeup_flag=(data[55] & 0x0F) if len(data) > 55 else 1,
        move_light_flag=((data[55] >> 4) & 0x0F) if len(data) > 55 else 1,
    )


def parse_buttons(data: bytes) -> list[ButtonAssignment]:
    """Parse button assignments from GET BUTTONS response."""
    if len(data) < 32 or data[0] != RSP_MAGIC or data[1] != CMD_GET_BUTTONS:
        return list(DEFAULT_BUTTONS)

    buttons = []
    for i in range(6):
        offset = 8 + i * 4
        if offset + 3 < len(data):
            btn = ButtonAssignment(
                index=i,
                type=data[offset],
                code1=data[offset + 1],
                code2=data[offset + 2],
                code3=data[offset + 3],
            )
            # If type is 0 or 0xFF, use default
            if btn.type == 0 or btn.type == 0xFF:
                buttons.append(DEFAULT_BUTTONS[i])
            else:
                buttons.append(btn)
        else:
            buttons.append(DEFAULT_BUTTONS[i])

    return buttons


def parse_connection_status(data: bytes) -> int:
    """Parse connection status from GET STATUS response."""
    if len(data) > 8:
        return data[8]
    return 0


def parse_push_report(data: bytes) -> Optional[dict]:
    """
    Parse unsolicited push reports sent by the mouse hardware in real time.
    """
    if not data or len(data) < 10 or data[0] != RSP_MAGIC:
        return None

    cmd_id = data[1]

    # Real-time DPI / Report Rate change event from physical button press
    if cmd_id == CMD_PUSH_DPI_STATUS and (data[8] != 0xD0 if len(data) > 8 else True):
        dpi_index = max(0, data[9] - 1) if len(data) > 9 else 0
        report_rate = max(0, min(3, data[10] - 1)) if len(data) > 10 else 3
        return {
            "event": "dpi_rate_changed",
            "dpi_index": dpi_index,
            "report_rate": report_rate
        }

    # Real-time Battery update event
    if cmd_id == CMD_GET_BATTERY:
        return {
            "event": "battery_updated",
            "battery": parse_battery(data)
        }

    # Real-time Connection status update event
    if cmd_id == CMD_GET_STATUS:
        return {
            "event": "status_updated",
            "status": parse_connection_status(data)
        }

    return None

