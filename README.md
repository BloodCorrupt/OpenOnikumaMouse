# OpenOnikumaMouse 🖱️⚡

An open-source Python driver API and modern **CustomTkinter Dark-Theme Desktop GUI** for the **Onikuma CW935** programmable gaming mouse (Instant S203 optical sensor).

Reverse-engineered directly from the vendor's official WebHID application protocol specs (`DM01`, `DM07`, `DM09`), this software enables complete hardware configuration, real-time status monitoring, and onboard EEPROM memory customization on Windows and Linux—without relying on closed-source web software or vendor drivers.

---

## 🌟 Key Features

- **🎛️ Full DPI Stage Customization (50 – 12,800 DPI)**
  - Configure up to 6 onboard DPI stages with precise 50 DPI steps.
  - **Real-Time DPI Push Events**: Instant updates in the GUI when changing DPI stages directly via physical mouse buttons.
- **🎯 Performance & Sensor Tuning**
  - Adjustable **USB Report Rate**: 125 Hz, 250 Hz, 500 Hz, 1000 Hz.
  - **Button Debounce Delay (Key Response)**: Fine-tune key debounce from 1 ms to 30 ms.
  - **Auto-Sleep Timeout**: Set wireless power-saving sleep timer (0 to 30 minutes).
  - **Roller Direction Invert**: Switch mouse wheel scroll direction (Forward / Reverse).
- **🕹️ 6-Button Macro & Remapping**
  - Rebind all 6 physical mouse buttons (Left, Right, Middle, Forward, Back, DPI Cycle) to presets: Media Play/Pause, Volume, Browser Nav, Boss Key, Fire Key, Triple Click, etc.
- **🌈 RGB Lighting Control & Static Color Mapping**
  - **7 Hardware Light Modes**: Wave, Neon, Touring Flash, YOYO Ball, Unidirectional Flashing, Circular Breathing, Turn Off The Light.
  - **Static Stage Colors**: Hardware static solid colors (Blue, Green, Yellow, Cyan, Magenta, White) bound directly to active DPI Stages 1 to 6.

- **🔋 Vendor-Accurate Battery Meter & Connection Mode**
  - Displays connection interface (**2.4G Wireless Dongle** vs **Wired USB**).
  - **Exact Vendor Lookup Mapping**: Implements the official WebHID battery range lookup table (10% to 100%) with charging indicator (`⚡`).
- **📌 Windows System Tray Integration & Executable Build**
  - Minimizes to system tray on window close (`X`).
  - Right-click tray menu options (`Show Onikuma CW935`, `Reconnect Mouse`, `Exit`).
  - Includes `build_exe.py` script to compile into a standalone Windows `.exe` (`dist/OnikumaCW935/OnikumaCW935.exe`).

---

## 📸 Screenshots

*(Run `python main.py` to launch the dark-theme control panel UI)*

---

## 📦 Requirements

- **Python 3.8+**
- **hidapi** (USB HID communication layer)
- **customtkinter** (Modern dark-theme UI components)
- **pystray** & **Pillow** (System tray icon support)

Install dependencies via pip:
```bash
pip install -r requirements.txt
```

---

## 🛠️ Build Standalone Windows Executable (.exe)

To compile the application into a standalone Windows executable (`.exe` with app icon):

```bash
python build_exe.py
```
The output executable will be generated at `dist/OnikumaCW935/OnikumaCW935.exe`.

---

## 🚀 Getting Started

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

## 💻 Python API Usage

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

## 📜 Reverse-Engineered HID Protocol Details

The Onikuma CW935 uses an **Instant S203** MCU/Sensor combo communicating via 65-byte USB Output Reports (`Report ID 0 + 64 bytes payload`).

- **Vendor Usage Page**: `0xFF01`, **Usage**: `0x10`
- **Output Report Header**: `0x00, 0x55` (`CMD_MAGIC`)
- **Key Command Magic Bytes**:
  - `0x0E`: `CMD_GET_CONFIG` (Fetch current DPI, report rate, lighting mode, sleep timer)
  - `0x0F`: `CMD_SET_CONFIG` (Persist settings to EEPROM)
  - `0x21`: `CMD_SET_LIGHT` (Live RGB light mode update `buf[3]=1, buf[5]=3, buf[11]=mode`)
  - `0x30`: `CMD_GET_BATTERY` (Fetch battery level & charging state)
  - `0xAA`: Hardware push report header (dispatched asynchronously on DPI button presses)

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
