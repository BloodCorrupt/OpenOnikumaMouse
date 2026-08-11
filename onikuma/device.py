"""
Onikuma CW935 HID Device Layer
==============================
Handles low-level USB/HID communication via `hidapi`.
Includes support for real-time background push event dispatching.
"""

import time
import logging
import threading
from typing import Optional, List, Callable
import hid  # type: ignore

from .protocol import (
    VID_WIRED, VID_WIRELESS, VID_ALT, PID_CW935, USAGE_PAGE, USAGE,
    WRITE_SIZE, PACKET_SIZE, RSP_MAGIC, parse_push_report
)

logger = logging.getLogger(__name__)

def find_devices() -> List[dict]:
    """
    Enumerate all connected HID devices matching Onikuma mouse VIDs/PIDs or usage filters.
    """
    matching_devices = []
    for d in hid.enumerate():
        vendor_id = d.get('vendor_id', 0)
        product_id = d.get('product_id', 0)
        usage_page = d.get('usage_page', 0)
        usage = d.get('usage', 0)

        # Check vendor ID match or Usage Page/Usage match
        is_vid_match = vendor_id in (VID_WIRED, VID_WIRELESS, VID_ALT)
        is_usage_match = (usage_page == USAGE_PAGE and usage == USAGE)

        if is_vid_match or is_usage_match:
            matching_devices.append(d)

    return matching_devices


class HIDDevice:
    """
    Wrapper around hid.device with connection management, thread safety, send/receive,
    and push event listener callbacks.
    """
    def __init__(self, path: Optional[bytes] = None, vendor_id: int = 0, product_id: int = 0, product_string: str = ""):
        self.path = path
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.product_string = product_string
        self._dev: Optional[hid.device] = None
        self.callbacks: List[Callable[[dict], None]] = []
        self.lock = threading.Lock()

    def register_callback(self, callback: Callable[[dict], None]):
        """Register a callback for real-time push events (DPI changes, battery, etc.)."""
        with self.lock:
            if callback not in self.callbacks:
                self.callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[dict], None]):
        """Unregister a callback."""
        with self.lock:
            if callback in self.callbacks:
                self.callbacks.remove(callback)

    def _dispatch_push_event(self, data: bytes):
        """Parse packet and notify registered listeners if it is a push event."""
        event_data = parse_push_report(data)
        if event_data:
            for cb in list(self.callbacks):
                try:
                    cb(event_data)
                except Exception as e:
                    logger.error(f"Error in push event callback: {e}")

    def open(self) -> bool:
        """Open the HID device connection."""
        with self.lock:
            if self._dev is not None:
                return True

            self._dev = hid.device()
            try:
                if self.path:
                    self._dev.open_path(self.path)
                else:
                    self._dev.open(self.vendor_id, self.product_id)
                self._dev.set_nonblocking(1)
                logger.info(f"Opened HID device: VID=0x{self.vendor_id:04X}, PID=0x{self.product_id:04X}")
                return True
            except Exception as e:
                logger.error(f"Failed to open HID device: {e}")
                self._dev = None
                return False

    def close(self):
        """Close the HID device connection."""
        with self.lock:
            if self._dev:
                try:
                    self._dev.close()
                except Exception as e:
                    logger.warning(f"Error closing HID device: {e}")
                self._dev = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def write(self, packet: bytes) -> int:
        """
        Write a 65-byte output report (Report ID 0 + 64 bytes payload).
        """
        with self.lock:
            if not self._dev:
                raise RuntimeError("Device not open")

            data = list(packet)
            if len(data) < WRITE_SIZE:
                data.extend([0] * (WRITE_SIZE - len(data)))
            elif len(data) > WRITE_SIZE:
                data = data[:WRITE_SIZE]

            written = self._dev.write(data)
            if written < 0:
                raise IOError("HID write failed")
            return written

    def read_single(self) -> bytes:
        """Read single report without waiting, dispatching any push events."""
        with self.lock:
            if not self._dev:
                return b""
            res = self._dev.read(PACKET_SIZE + 1)
            if res:
                b_res = bytes(res)
                self._dispatch_push_event(b_res)
                return b_res
            return b""

    def read(self, timeout_ms: int = 500) -> bytes:
        """
        Read a HID report with non-blocking polling and timeout.
        Dispatches any push events received while waiting.
        """
        start_time = time.time()
        timeout_sec = timeout_ms / 1000.0

        while (time.time() - start_time) < timeout_sec:
            with self.lock:
                if not self._dev:
                    raise RuntimeError("Device not open")
                res = self._dev.read(PACKET_SIZE + 1)
                if res:
                    b_res = bytes(res)
                    self._dispatch_push_event(b_res)
                    return b_res
            time.sleep(0.005)

        return b""

    def send_command(self, cmd_packet: bytes, expected_cmd: Optional[int] = None, timeout_ms: int = 500, retries: int = 3) -> bytes:
        """
        Send a command packet and wait for a matching response (0xAA header).
        Flushes unread reports (and dispatches any push events) before sending.
        """
        if not self._dev and not self.open():
            raise RuntimeError("Unable to open device")

        for attempt in range(retries):
            # Flush unread reports
            with self.lock:
                while self._dev:
                    junk = self._dev.read(PACKET_SIZE + 1)
                    if not junk:
                        break
                    self._dispatch_push_event(bytes(junk))

                # Send command
                if not self._dev:
                    break
                data = list(cmd_packet)
                if len(data) < WRITE_SIZE:
                    data.extend([0] * (WRITE_SIZE - len(data)))
                elif len(data) > WRITE_SIZE:
                    data = data[:WRITE_SIZE]
                self._dev.write(data)

            # Wait for response
            response = self.read(timeout_ms=timeout_ms)
            if response and response[0] == RSP_MAGIC:
                if expected_cmd is None or (len(response) > 1 and response[1] == expected_cmd):
                    return response

            time.sleep(0.05)

        return b""

