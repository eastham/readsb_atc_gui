#!/usr/bin/python3
"""
Accept traffic over a port from readsb and send slack messages when 
aircraft matching argument KML are seen.

TODO:
- maybe also log to appsheet?  
"""

import datetime
import json
import requests
import time
import threading

import adsb_receiver
from dbg import dbg, set_dbg_level, log
from bboxes import Bboxes
from config import Config
from adsb_receiver import Flights
from flight import Flight, Location

import appsheet_api

SEND_SLACK = True
TZ_CONVERT = 0 # -7  # UTC conversion
API_LOOP_DELAY = 300  # seconds
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

def api_read_loop(bbox_list, bbox_cb):
    flights = Flights(bbox_list)
    headers = {
        "X-RapidAPI-Key": CONFIG.private_vars['rapid_api_key'],
        "X-RapidAPI-Host": "adsbexchange-com1.p.rapidapi.com"
    }

    while True:
        response = requests.get(CONFIG.private_vars['adsbx_url'], headers=headers, timeout=20)
        jsondict = response.json()
        print(jsondict)
        try:
            for ac in jsondict['ac']:
                loc_update = Location.from_dict(ac)
                print(loc_update)
                flights.add_location(loc_update, None, None, bbox_cb)
        except Exception as e:
            print("api error: " + str(e))

        print("Sleeping ")
        time.sleep(API_LOOP_DELAY)


if __name__ == "__main__":
    # No-GUI mode, see controller.py for GUI
    import argparse

    parser = argparse.ArgumentParser(description="match flights against kml bounding boxes")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument('file', nargs='+', help="kml files to use")
    parser.add_argument('--ipaddr', help="IP address to connect to")
    parser.add_argument('--port', help="port to connect to")
    parser.add_argument('--api', action='store_true',
                        help="use web api instead of direct connect IP")
    args = parser.parse_args()

    if args.debug: set_dbg_level(2)
    else: set_dbg_level(1)
    bboxes_list = []
    for f in args.file:
        bboxes_list.append(Bboxes(f))

    if args.api:
        api_read_loop(bboxes_list, bbox_start_change_cb)
    else:
        listen = adsb_receiver.setup(args.ipaddr, args.port)
        adsb_receiver.flight_read_loop(listen, bboxes_list, None, None,
            None, bbox_start_change_cb)
