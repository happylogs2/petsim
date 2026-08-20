"""
Validates every zone config referenced by devices.json before the fleet
launches - catches a typo'd path or missing template image in one pass,
instead of watching it surface as fifteen staggered failures over the
next 45 seconds of startup.

Run standalone: python validate_configs.py
Also called automatically at the top of orchestrator.main().
"""
import json
import sys
from pathlib import Path

import vision

REQUIRED_ZONE_KEYS = ["portal_check_region", "unlocked_template_path", "waypoints"]
VALID_ACTIONS = ("hold_joystick", "tap", "wait")


def validate_zone_config(path: str, visited: set) -> list:
    """Returns a list of error strings (empty = valid). Follows next_zone_config recursively."""
    if path in visited:
        return []  # already validated this chain, avoid infinite loops on circular configs
    visited.add(path)

    p = Path(path)
    if not p.exists():
        return [f"{path}: file not found"]

    try:
        cfg = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        return [f"{path}: invalid JSON ({e})"]

    errors = []
    for key in REQUIRED_ZONE_KEYS:
        if key not in cfg:
            errors.append(f"{path}: missing required key '{key}'")

    region = cfg.get("portal_check_region")
    if region is not None and (not isinstance(region, list) or len(region) != 4):
        errors.append(f"{path}: portal_check_region must be [x, y, w, h]")

    template_path = cfg.get("unlocked_template_path")
    if template_path:
        try:
            vision.load_template(template_path)
        except FileNotFoundError:
            errors.append(f"{path}: unlocked_template_path '{template_path}' not found")

    waypoints = cfg.get("waypoints")
    if waypoints is not None and not isinstance(waypoints, list):
        errors.append(f"{path}: waypoints must be a list")
    elif isinstance(waypoints, list):
        if len(waypoints) == 0:
            errors.append(f"{path}: waypoints is empty - bot won't move")
        for i, step in enumerate(waypoints):
            action = step.get("action")
            if action not in VALID_ACTIONS:
                errors.append(f"{path}: waypoints[{i}] has unknown action '{action}'")
            elif action == "hold_joystick" and ("center" not in step or "offset" not in step):
                errors.append(f"{path}: waypoints[{i}] hold_joystick missing 'center' or 'offset'")
            elif action == "tap" and "pos" not in step:
                errors.append(f"{path}: waypoints[{i}] tap missing 'pos'")

    threshold = cfg.get("match_threshold", 0.85)
    if not (0 < threshold <= 1):
        errors.append(f"{path}: match_threshold {threshold} should be between 0 and 1")

    next_cfg = cfg.get("next_zone_config")
    if next_cfg:
        errors.extend(validate_zone_config(next_cfg, visited))

    return errors


def validate_devices(devices_config_path: str) -> bool:
    """Returns True if everything is valid. Prints every problem found."""
    if not Path(devices_config_path).exists():
        print(f"{devices_config_path} not found.")
        return False

    with open(devices_config_path) as f:
        devices = json.load(f)

    all_errors = []
    seen_serials = set()
    visited_zones = set()

    for dev in devices:
        serial = dev.get("serial")
        if not serial:
            all_errors.append("device entry missing 'serial'")
            continue
        if serial in seen_serials:
            all_errors.append(f"duplicate serial: {serial}")
        seen_serials.add(serial)

        zone_config = dev.get("zone_config")
        if not zone_config:
            all_errors.append(f"{serial}: missing 'zone_config'")
            continue

        all_errors.extend(validate_zone_config(zone_config, visited_zones))

    if all_errors:
        print(f"Found {len(all_errors)} config problem(s):")
        for err in all_errors:
            print(f"  - {err}")
        return False

    print(f"All good: {len(devices)} device(s), {len(visited_zones)} zone config(s) validated.")
    return True


if __name__ == "__main__":
    ok = validate_devices("config/devices.json")
    sys.exit(0 if ok else 1)
