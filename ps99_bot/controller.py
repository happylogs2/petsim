"""
Device controller: wraps ADB commands for a single Roblox/LDPlayer instance.

Default backend uses plain `adb shell input` calls (works out of the box,
no extra setup). For 15+ concurrent instances, swap in a minitouch backend
later to cut per-action latency from ~150-300ms down to ~5-10ms - each
`adb shell input` call forks a new process on the device/emulator, which
adds up fast when 15 loops are polling constantly. See README for the
upgrade path.
"""
import subprocess
import numpy as np
import cv2


class DeviceController:
    def __init__(self, serial: str, adb_path: str = "adb"):
        self.serial = serial
        self.adb_path = adb_path

    def _adb(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.adb_path, "-s", self.serial, *args],
            capture_output=True, timeout=10
        )

    def tap(self, x: int, y: int):
        self._adb("shell", "input", "tap", str(x), str(y))

    def swipe(self, x1, y1, x2, y2, duration_ms=300):
        self._adb("shell", "input", "swipe",
                   str(x1), str(y1), str(x2), str(y2), str(duration_ms))

    def hold_joystick(self, center, offset, duration_s: float, steps: int = 6):
        """
        Simulates holding a virtual joystick in a direction.

        `center` is the joystick's resting position on screen (x, y).
        `offset` is (dx, dy) - how far to push toward, relative to center.
        Roblox's mobile joystick reads continuous position, so a single
        swipe often gets ignored for sustained movement. Issuing several
        short swipes back to the same held point holds the direction instead.
        """
        cx, cy = center
        tx, ty = cx + offset[0], cy + offset[1]
        step_dur = max(1, int((duration_s * 1000) / steps))
        for _ in range(steps):
            self.swipe(cx, cy, tx, ty, step_dur)

    def screencap(self) -> np.ndarray:
        """Returns the current screen as a BGR numpy array (OpenCV format)."""
        result = self._adb("exec-out", "screencap", "-p")
        img_array = np.frombuffer(result.stdout, dtype=np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return frame

    def is_connected(self) -> bool:
        result = subprocess.run([self.adb_path, "devices"], capture_output=True, text=True)
        return self.serial in result.stdout
