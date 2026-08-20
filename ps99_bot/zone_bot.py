"""
Per-instance state machine. One ZoneBot runs one Roblox account through
a wait-for-currency -> walk-to-portal -> transition loop, using whatever
zone config is currently loaded. Each zone config points to the next
one, so a bot chains through zones on its own once started.
"""
import time
import json
from enum import Enum, auto

from controller import DeviceController
import vision
import status_store


class State(Enum):
    WAITING_FOR_UNLOCK = auto()
    TRAVELING_TO_PORTAL = auto()
    TRANSITIONING = auto()


class ZoneBot:
    def __init__(self, device: DeviceController, zone_config_path: str, poll_interval: float = 2.0,
                 account_name: str = "", roblox_username: str = ""):
        self.device = device
        self.poll_interval = poll_interval
        self.state = State.WAITING_FOR_UNLOCK
        self.account_name = account_name
        self.roblox_username = roblox_username
        self.load_zone_config(zone_config_path)

    def report_status(self):
        status_store.update_bot_state(
            serial=self.device.serial,
            account_name=self.account_name,
            roblox_username=self.roblox_username,
            current_zone=self.zone_name,
            state=self.state.name,
        )

    def load_zone_config(self, path: str):
        with open(path) as f:
            cfg = json.load(f)
        self.zone_name = cfg.get("zone_name", path)                  # human-readable label for the dashboard
        self.portal_region = tuple(cfg["portal_check_region"])       # (x, y, w, h)
        self.unlocked_template = vision.load_template(cfg["unlocked_template_path"])
        self.match_threshold = cfg.get("match_threshold", 0.85)
        self.waypoints = cfg["waypoints"]                            # list of action dicts
        self.transition_wait_s = cfg.get("transition_wait_s", 4.0)
        self.next_zone_config = cfg.get("next_zone_config")          # path to chain into, or None
        self.report_status()

    def portal_unlocked(self) -> bool:
        frame = self.device.screencap()
        region = vision.crop(frame, self.portal_region)
        return vision.matches(region, self.unlocked_template, self.match_threshold)

    def execute_waypoints(self):
        for step in self.waypoints:
            action = step["action"]
            if action == "hold_joystick":
                self.device.hold_joystick(
                    center=tuple(step["center"]),
                    offset=tuple(step["offset"]),
                    duration_s=step["duration"],
                )
            elif action == "tap":
                self.device.tap(*step["pos"])
            elif action == "wait":
                time.sleep(step["seconds"])

    def run_forever(self):
        while True:
            if self.state == State.WAITING_FOR_UNLOCK:
                if self.portal_unlocked():
                    self.state = State.TRAVELING_TO_PORTAL
                    self.report_status()
                else:
                    time.sleep(self.poll_interval)

            elif self.state == State.TRAVELING_TO_PORTAL:
                self.execute_waypoints()
                self.state = State.TRANSITIONING
                self.report_status()

            elif self.state == State.TRANSITIONING:
                time.sleep(self.transition_wait_s)
                if self.next_zone_config:
                    self.load_zone_config(self.next_zone_config)  # this also reports status
                self.state = State.WAITING_FOR_UNLOCK
                self.report_status()
