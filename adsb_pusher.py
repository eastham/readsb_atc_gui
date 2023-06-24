#!/usr/bin/python3
"""
Accept traffic over a port from readsb and push relevant flights to
an appsheet app.
"""

from collections import defaultdict
import datetime
import time
import threading
import pytz

import adsb_receiver
from dbg import dbg, set_dbg_level, log
from bboxes import Bboxes
import appsheet_api

as_instance = appsheet_api.Appsheet()
debug_stats = defaultdict(int)  # count by operation type sent to server

def lookup_or_create_aircraft(flight):
    """
    Return appsheet id for flight, checking w/ server if needed,
    creating if needed.
    """

    flight_id = flight.tail
    if not flight_id:
        flight_id = flight.flight_id

    if flight.external_id:
        return flight.external_id

    # id not cached locally
    with flight.threadlock:
        if flight.external_id:  # recheck in case we were preempted
            return flight.external_id
        aircraft_external_id = as_instance.aircraft_lookup(flight_id)
        if not aircraft_external_id:
            aircraft_external_id = as_instance.add_aircraft(flight_id)
            log("LOOKUP added aircraft and now has aircraft_external_id %s" % aircraft_external_id)
        else:
            log("LOOKUP got cached aircraft_external_id %s" % aircraft_external_id)

        flight.external_id = aircraft_external_id

    return flight.external_id

def bbox_start_change_cb(flight, flight_str):
    dbg("*** bbox_start_change_cb "+flight_str)
    t = threading.Thread(target=bbox_change_cb, args=[flight, flight_str])
    t.start()

def bbox_change_cb(flight, flight_str):
    """
    Called on all bbox changes, but only log to appsheet when LOGGED_BBOXES are entered.
    Also take note and log it later if NOTED_BBOX is seen.
    """

    LOGGED_BBOXES = ['Landing', 'Takeoff']
    NOTED_BBOX = 'Pattern'
    FINAL_BBOX = 'Landing' # Must be in LOGGED_BBOXES.  When seen clears note about NOTED_BBOX.

    utc_time = datetime.datetime.utcfromtimestamp(flight.lastloc.now)
    log(f"*** bbox_change_cb at {utc_time}: {flight_str}")
    debug_stats["bbox_change"] += 1

    logged_bbox = next((b for b in LOGGED_BBOXES if b in flight_str), None)
    flight_id = flight.tail
    flight_name = flight.flight_id.strip()
    if not flight_id:
        flight_id = flight_name

    if NOTED_BBOX in flight_str:
        debug_stats[NOTED_BBOX] += 1
        flight.flags[NOTED_BBOX] = True

    if logged_bbox:
        debug_stats[logged_bbox] += 1
        noted = NOTED_BBOX in flight.flags
        dbg("adsb_pusher adding " + logged_bbox + " with note " + str(noted))

        aircraft_internal_id = lookup_or_create_aircraft(flight)

        as_instance.add_op(aircraft_internal_id, flight.lastloc.now,
                            noted, logged_bbox, flight_name)

    if logged_bbox is FINAL_BBOX:
        try:
            del flight.flags[NOTED_BBOX]
        except Exception:
            pass


class CPE:
    """ 
    Track CPE events.  These are pushed to the server when initially seen,
    updated locally when additional callbacks come in, and re-pushed to the
    server with the final stats once the event is gc'ed.
    """
    current_cpes = {}
    current_cpe_lock: threading.Lock = threading.Lock()
    CPE_GC_TIME = 60
    gc_thread = None

    def __init__(self, flight1, flight2, latdist, altdist, create_time):
        # keep these in a universal order to enforce lock ordering and consistent keys
        if flight1.flight_id > flight2.flight_id:
            self.flight2 = flight1
            self.flight1 = flight2
        else:
            self.flight1 = flight1
            self.flight2 = flight2
        self.latdist = self.min_latdist = latdist
        self.altdist = self.min_altdist = altdist
        self.create_time = self.last_time = create_time
        self.id = None

    def update(self, latdist, altdist, last_time):
        self.latdist = latdist
        self.altdist = altdist
        self.last_time = last_time
        # perhaps this is better done with an absolute distance?
        if latdist <= self.min_latdist or altdist <= self.min_altdist:
            self.min_latdist = latdist
            self.min_altdist = altdist

    def key(self):
        key = "%s %s" % (self.flight1.flight_id.strip(),
            self.flight2.flight_id.strip())
        return key

def cpe_start_cb(flight1, flight2, latdist, altdist):
    t = threading.Thread(target=cpe_cb, args=[flight1, flight2, latdist, altdist])
    t.start()

def cpe_cb(flight1, flight2, latdist, altdist):
    if not CPE.gc_thread:
        CPE.gc_thread = threading.Thread(target=gc_loop)
        CPE.gc_thread.start()

    dbg("CPE_CB " + flight1.flight_id + " " + flight2.flight_id)

    now = flight1.lastloc.now
    # always create a new CPE at least to get flight1/flight2 ordering right
    cpe = CPE(flight1, flight2, latdist, altdist, now)

    CPE.current_cpe_lock.acquire()
    key = cpe.key()
    if key in CPE.current_cpes:
        dbg("CPE update " + key)
        CPE.current_cpes[key].update(latdist, altdist, now)
        debug_stats["CPE update"] += 1
        CPE.current_cpe_lock.release()
    else:
        dbg("CPE add " + key)
        CPE.current_cpes[key] = cpe
        debug_stats["CPE add"] += 1
        CPE.current_cpe_lock.release()

        flight1_internal_id = lookup_or_create_aircraft(cpe.flight1)
        flight2_internal_id = lookup_or_create_aircraft(cpe.flight2)

        cpe.id = as_instance.add_cpe(flight1_internal_id, flight2_internal_id,
            latdist, altdist, now)

def gc_loop():
    while True:
        time.sleep(10)
        cpe_gc()

def cpe_gc():
    dbg("CPE_GC")
    with CPE.current_cpe_lock:
        cpe_list = list(CPE.current_cpes.values())

    for cpe in cpe_list:
        dbg(f"CPE_GC {cpe.key()} {time.time()} {cpe.last_time}")

        # NOTE: time.time() doesn't behave correctly here in replay mode.
        if time.time() - cpe.last_time > CPE.CPE_GC_TIME:
            dbg(f"CPE final update {cpe.flight1.flight_id} {cpe.flight2.flight_id}")
            debug_stats["CPE finalize"] += 1

            flight1_internal_id = lookup_or_create_aircraft(cpe.flight1)
            flight2_internal_id = lookup_or_create_aircraft(cpe.flight2)

            as_instance.update_cpe(flight1_internal_id, flight2_internal_id,
                cpe.min_latdist, cpe.min_altdist, cpe.create_time, cpe.id)
            try:
                del CPE.current_cpes[cpe.key()]
            except Exception:
                print("Error: didn't find key in current_cpes")
                pass


def test_cb():
    t = threading.Thread(target=test_cb_body)
    t.start()

def test_cb_body():
    log("TEST THREAD RUNNING.  Stats:")
    print_stats()
    now = datetime.datetime.now()

    pacific_tz = pytz.timezone('America/Los_Angeles')
    pacific_time = now.astimezone(pacific_tz)
    desc = "TEST AT day/hr: %d/%d" % (pacific_time.day,pacific_time.hour)

    as_instance.add_aircraft("N123XXX", test=True, description=desc)

def print_stats():
    for key, value in debug_stats.items():
        if value != 0:
            print(f"{key}: {value}")

if __name__ == "__main__":
    # No-GUI mode, see controller.py for GUI
    import argparse

    parser = argparse.ArgumentParser(description="match flights against kml bounding boxes")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument('--test', help="add some test flights", action="store_true")
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
        cpe_start_cb, bbox_start_change_cb, test_cb=test_cb)
