"""
Runs one ZoneBot per configured device, each in its own process.

Multiprocessing, not threading: screencap decode + template matching is
CPU-bound, so threads would fight over the GIL once you're running 15
instances. Separate processes actually use your cores.
"""
import json
import signal
import sys
import time
from multiprocessing import Process

from controller import DeviceController
from zone_bot import ZoneBot
from validate_configs import validate_devices
import status_store


def run_instance(serial: str, zone_config_path: str, start_delay: float,
                  account_name: str, roblox_username: str):
    time.sleep(start_delay)  # stagger so 15 instances don't spike CPU on the same tick
    device = DeviceController(serial)
    if not device.is_connected():
        print(f"[{serial}] not connected, skipping")
        return
    bot = ZoneBot(device, zone_config_path, account_name=account_name, roblox_username=roblox_username)
    print(f"[{serial}] starting")
    bot.run_forever()


def main(devices_config_path: str, stagger_s: float = 3.0):
    if not validate_devices(devices_config_path):
        print("Fix the config problems above before launching.")
        sys.exit(1)

    status_store.init_db()

    with open(devices_config_path) as f:
        devices = json.load(f)

    processes = []
    for i, dev in enumerate(devices):
        p = Process(
            target=run_instance,
            args=(
                dev["serial"],
                dev["zone_config"],
                i * stagger_s,
                dev.get("account_name", dev["serial"]),
                dev.get("roblox_username", ""),
            ),
        )
        p.start()
        processes.append(p)

    def shutdown(signum, frame):
        print("\nStopping all instances...")
        for p in processes:
            if p.is_alive():
                p.terminate()
        for p in processes:
            p.join(timeout=5)
        print("All instances stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    for p in processes:
        p.join()


if __name__ == "__main__":
    main("config/devices.json")
