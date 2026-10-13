"""Simulated wearable that sends synthetic readings to the API.

FR6: a heart-rate reading and the day's cumulative step count every 5 minutes.
FR7: one sleep-duration summary each day.

Usage:
    python simulator.py --device-id DEV-XXXXXXXX --token YOUR_TOKEN
    python simulator.py --device-id ... --token ... --interval 5   (faster, for testing)
"""

import argparse
import json
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

RIYADH = ZoneInfo("Asia/Riyadh")


def send(url, device_id, token, reading_type, value):
    body = json.dumps({
        "device_id": device_id,
        "type": reading_type,
        "value": value,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }).encode()
    request = urllib.request.Request(
        url + "/api/readings", data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
    )
    try:
        with urllib.request.urlopen(request) as response:
            print(reading_type, value, "->", response.status, response.read().decode().strip())
    except urllib.error.HTTPError as e:
        print(reading_type, value, "->", e.code, e.read().decode().strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5000")
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--interval", type=int, default=300, help="seconds between readings (FR6: 300)")
    parser.add_argument("--count", type=int, default=0, help="stop after this many rounds (0 = run forever)")
    args = parser.parse_args()

    steps = 0
    day = datetime.now(RIYADH).date()
    send(args.url, args.device_id, args.token, "sleep", round(random.uniform(5, 9), 1))

    rounds = 0
    while True:
        today = datetime.now(RIYADH).date()
        if today != day:  # new day: reset steps and send last night's sleep (FR7)
            day, steps = today, 0
            send(args.url, args.device_id, args.token, "sleep", round(random.uniform(5, 9), 1))

        steps += random.randint(0, 600)
        send(args.url, args.device_id, args.token, "heart_rate", random.randint(55, 110))
        send(args.url, args.device_id, args.token, "steps", steps)

        rounds += 1
        if args.count and rounds >= args.count:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
