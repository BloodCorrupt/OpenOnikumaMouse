# OpenOnikumaMouse

An open-source Python driver API, terminal CLI, and modern **PySide6 Dark-Theme Desktop GUI** for the **Onikuma CW935** programmable gaming mouse (Instant S203 optical sensor).

Reverse-engineered directly from the vendor's official WebHID application protocol specs (`DM01`, `DM07`, `DM09`), this software enables complete hardware configuration, real-time status monitoring, and onboard EEPROM memory customization on Windows and Linux—without relying on closed-source web software or vendor drivers.

---

## Key Features

- **Modern PySide6 Control Suite**
  - Dark obsidian & electric cyan interface with unified bordered cards, non-blocking toast notifications, and custom `QPainter` vector line-art sidebar icons.
  - Live profile telemetry summary (active DPI & polling rate) and automatic background device discovery.
- **Full DPI Stage Customization (50 – 12,800 DPI)**
  - Configure up to 6 onboard DPI stages with 50 DPI step precision, synced sliders & spinboxes, and color-coded stage indicators.
  - **Real-Time DPI Push Events**: Instant UI updates when switching DPI stages directly via physical mouse buttons.
- **Performance & Sensor Tuning**
  - **USB Polling Rate**: `125 Hz`, `250 Hz`, `500 Hz`, `1000 Hz`.
  - **Lift-Off Distance (LOD)**: `Low (1 mm)` / `High (2 mm)`.
  - **Button Debounce Delay**: Fine-tune key response from `1 ms` to `30 ms`.
  - **Auto-Sleep Timeout**: Wireless power-saving timer (`0` = Off, `1–30` minutes).
  - **Scroll Wheel Direction**: Switch between `Forward (Normal)` and `Reverse (Inverted)`.
- **Interactive 6-Button Mapping**
  - Clickable top-down vector mouse diagram (`MousePreviewWidget`) paired with 6 programmable button slots (Left, Right, Middle, Back, Forward, DPI Button).
  - Supports mouse functions, media controls, fire key, and button disable presets, plus one-click factory button reset.
- **Live RGB Lighting Simulation & Control**
  - **7 Hardware Light Modes**: Wave, Neon, Touring Flash, YOYO Ball, Unidirectional Flashing, Circular Breathing, and Turn Off The Light.
  - Real-time animated RGB preview on the mouse silhouette reflecting the active mode and DPI stage color.
  - **Static Stage Colors**: Hardware static solid colors (Blue, Green, Yellow, Cyan, Magenta, White) bound to active DPI Stages 1–6.
- **Battery Gauge, Diagnostics & System Tray**
  - Custom-painted battery level pill with charging indicator (`⚡`) and connection mode badge (**Wired USB** vs **2.4G Wireless Dongle**).
  - Native `QSystemTrayIcon` integration (minimizes to tray on close; context menu with Show, Reconnect Mouse, Exit).
  - Includes `build_exe.py` to compile a standalone Windows executable (`dist/OnikumaCW935/OnikumaCW935.exe`).

---

## Requirements

- **Python 3.10+**
- **PySide6** (Qt6 desktop GUI & system tray)
- **hidapi** (USB HID communication layer)
- **rich** (Terminal CLI formatting)
- **pyinstaller** (Optional, for building standalone `.exe`)

Install dependencies via pip:

```bash
pip install -r requirements.txt
```

---

## Getting Started

### 1. Launch the Desktop GUI
Connect your Onikuma CW935 mouse via USB cable or 2.4G wireless dongle, then run:

```bash
python main.py
```

### 2. Launch Terminal CLI
For headless environments or command-line scripting:

```bash
python main.py --cli
```

---

## Build Standalone Windows Executable (.exe)

To compile the application into a standalone Windows executable with embedded assets:

```bash
python build_exe.py
```

The output executable will be generated at `dist/OnikumaCW935/OnikumaCW935.exe`.

---

## Project Structure

```text
├── main.py                 # Application entry point (GUI default, --cli for terminal)
├── build_exe.py            # PyInstaller build script
├── requirements.txt        # Python dependencies
├── assets/                 # Application icons (icon.ico, icon.png)
└── onikuma/
    ├── gui.py              # PySide6 main window, pages, and system tray integration
    ├── widgets.py          # Custom QPainter widgets (MousePreviewWidget, BatteryBadgeWidget, EffectCard, ToastNotification, vector icons)
    ├── theme.py            # Dark obsidian QSS stylesheet and design tokens
    ├── mouse.py            # High-level OnikumaCW935 controller API
    ├── protocol.py         # Reverse-engineered 64-byte HID command builders & parsers
    ├── device.py           # Cross-platform HID device discovery & I/O wrapper
    └── cli.py              # Interactive terminal CLI
```

---

## Python API Usage

You can also use the high-level `OnikumaCW935` Python API directly in your own scripts:

```python
from onikuma import OnikumaCW935, LightMode

# Connect to mouse (Auto-detected via Vendor ID / Usage Page)
with OnikumaCW935() as mouse:
    # Read Device & Battery Info
    info = mouse.get_info()
    battery = mouse.get_battery()
    print(f"Connected: {info.connection_mode}")
    print(f"Battery: {battery.percentage}% (Charging: {battery.charging})")

    # Set DPI Stages (Stage 1..6) and activate Stage 2 (1600 DPI)
    mouse.set_dpi_stages([800, 1600, 2400, 3200, 5000, 12000], active_index=1)

    # Set USB Polling Rate to 1000 Hz
    mouse.set_report_rate(1000)

    # Set RGB Lighting Effect (Wave mode)
    mouse.set_light_mode(LightMode.WAVE)
```

---

## Reverse-Engineered HID Protocol Details

The Onikuma CW935 uses an **Instant S203** MCU/Sensor combo communicating via 65-byte USB Output Reports (`Report ID 0 + 64 bytes payload`).

- **Vendor Usage Page**: `0xFF01`, **Usage**: `0x10`
- **Output Report Header**: `0x00, 0x55` (`CMD_MAGIC`)
- **Key Command Magic Bytes**:
  - `0x0E`: `CMD_GET_CONFIG` (Fetch current DPI, report rate, lighting mode, LOD, sleep timer)
  - `0x0F`: `CMD_SET_CONFIG` (Persist settings to EEPROM)
  - `0x21`: `CMD_SET_LIGHT` (Live RGB light mode update `buf[3]=1, buf[5]=3, buf[11]=mode`)
  - `0x30`: `CMD_GET_BATTERY` (Fetch battery level & charging state)
  - `0xAA`: Hardware push report header (dispatched asynchronously on DPI button presses)

---

## License

Distributed under the MIT License. See `LICENSE` for more information.
