#!/usr/bin/python3
"""
Accept traffic over a port from readsb and send slack messages when 
aircraft matching argument KML are seen.

TODO:
- maybe also log to appsheet?  
"""

from collections import defaultdict
import datetime
import requests
import time
import threading
import pytz

import adsb_receiver
from dbg import dbg, set_dbg_level, log
from bboxes import Bboxes
from config import Config

import appsheet_api

SEND_SLACK = True
TZ_CONVERT = 0 # -7  # UTC conversion
CONFIG = Config()

def send_slack(text):
    print(f"Slack msg: {text}")
    if SEND_SLACK:
        webhook = CONFIG.private_vars['slack_nearby_webhook']
        payload = {"text": text}
        response = requests.post(webhook, json.dumps(payload))
        print(response)
    else:
        print("Skipping slack send")

def bbox_start_change_cb(flight, flight_str):
    dbg("*** bbox_start_change_cb "+flight_str)
    t = threading.Thread(target=bbox_change_cb, args=[flight, flight_str])
    t.start()

def bbox_change_cb(flight, flight_str):
    local_time = datetime.datetime.fromtimestamp(flight.lastloc.now)
    log(f"*** bbox_change_cb at {local_time}: {flight_str}")

    flight_id = flight.tail
    flight_name = flight.flight_id.strip()
    if not flight_id:
        flight_id = flight_name

    if "Nearby" in flight_str:
        send_slack(flight_str)


if __name__ == "__main__":
    # No-GUI mode, see controller.py for GUI
    import argparse

    parser = argparse.ArgumentParser(description="match flights against kml bounding boxes")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument('file', nargs='+', help="kml files to use")
    parser.add_argument('--ipaddr', help="IP address to connect to", required=True)
    parser.add_argument('--port', help="port to connect to", required=True)
    args = parser.parse_args()

    if args.debug: set_dbg_level(2)
    else: set_dbg_level(1)
    bboxes_list = []
    for f in args.file:
        bboxes_list.append(Bboxes(f))

    listen = adsb_receiver.setup(args.ipaddr, args.port)

    adsb_receiver.flight_read_loop(listen, bboxes_list, None, None,
        None, bbox_start_change_cb)
