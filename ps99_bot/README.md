# PS99 Multi-Zone Bot

State machine per account: wait for portal to unlock (coin threshold met)
-> walk to portal via a recorded input sequence -> transition -> repeat
with the next zone's config. No real-time pathfinding - zone layouts are
static, so you record the walk once per zone and reuse it forever.

## Setup

1. `pip install -r requirements.txt`
2. Get `adb` on your PATH (comes with LDPlayer, or install platform-tools).
3. Confirm you can see all instances: `adb devices` should list each
   LDPlayer serial (e.g. `127.0.0.1:5555`, `127.0.0.1:5557`, ...).

## Per-zone setup (do this once per zone, reuse forever)

For each zone the bot needs to pass through:

1. **Capture the portal-unlocked template.** On one instance, get the
   portal to its unlocked visual state (whatever changes - icon color,
   a glow, a checkmark), screenshot it, and crop out just that small
   region. Save as `config/templates/<zone>_unlocked.png`.
2. **Find the crop coordinates.** Note the `(x, y, w, h)` of that same
   region on the full screenshot - that's `portal_check_region`.
3. **Record the walk.** Figure out the joystick center position and
   which direction/duration gets you from spawn to the portal. Test
   values manually with `controller.py`'s `hold_joystick()` before
   locking them into a zone config.
4. Copy `config/zones/example_zone.json` to `config/zones/<zone>.json`,
   fill in the four values above, and set `next_zone_config` to chain
   into the following zone (or omit it on the last one).

## Running

1. Copy `config/devices.example.json` to `config/devices.json`, list
   every instance's serial and which zone config it should start from
   (accounts at different progress start from different zones).
2. `python orchestrator.py`

Each instance runs in its own process and logs `[serial] starting`.

## Live status dashboard

Three independent pieces run alongside each other:

1. **`orchestrator.py`** — runs the bots. Each one writes its current zone and
   state (waiting / traveling / loading) into `status.db` on every transition.
2. **`api_poller.py`** — reads `config/devices.json`, and for every account
   with a `roblox_username` set, polls the official BIG Games public player
   API every 5 minutes for exact Diamonds and world-coin balances, writing
   them into the same `status.db`.
3. **`dashboard/app.py`** — a small Flask app that reads `status.db` and
   serves a single status page at `http://localhost:5050`, auto-refreshing
   every 5 seconds.

**Setup for the API poller:** each account needs its "profile" view toggled
public from the in-game dashboard (look for a profile visibility / privacy
setting — exact menu placement may vary by client version). This is a
one-time flip per account, doesn't require OAuth, and doesn't expose
anything sensitive (no gamepasses, no Robux spend — that's a separate,
still-private view). Then set that account's exact Roblox username in
`config/devices.json`.

Run all three in separate terminals:

```
python orchestrator.py
python api_poller.py
python dashboard/app.py
```

Then open `http://localhost:5050`. Note the stats side updates on a ~5
minute cadence (matches the API's own cache window) — the zone/state side
updates instantly since it comes straight from the bots, not the network.

## Efficiency upgrade path (once the basic loop is working)

The default backend uses `adb shell input tap/swipe`, which forks a new
process on the emulator per call - fine at first, but adds up once 15
loops are polling constantly. Two swaps worth making once you've
validated the logic works:

- **Input**: switch `DeviceController` to use **minitouch** (STF
  toolkit) instead of `adb shell input`. Minitouch keeps a persistent
  socket open per instance instead of spawning a process per action -
  the single biggest latency win at this scale.
- **Capture**: switch `screencap()` to **minicap** or a scrcpy raw
  frame socket instead of `adb exec-out screencap`, which does a full
  PNG encode/decode round trip every call.

Both are drop-in replacements for the corresponding methods in
`controller.py` - the state machine and orchestrator don't need to change.
