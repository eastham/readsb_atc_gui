# accept traffic from readsb and push relevant flights to
# an appsheet app.

import datetime
import time
from threading import Thread
import pytz

import adsb_receiver
from dbg import dbg, set_dbg_level, log
from bboxes import Bboxes
import appsheet_api

as_instance = appsheet_api.Appsheet()

def lookup_or_create_aircraft(flight):
    '''return appsheet id for flight, creating if needed.'''

    flight_id = flight.tail
    if not flight_id:
        flight_id = flight.flight_id

    if not flight.external_id:
        aircraft_external_id = as_instance.aircraft_lookup(flight_id)
        if not aircraft_external_id:
            aircraft_external_id = as_instance.add_aircraft(flight_id)
            log("LOOKUP added aircraft and now has aircraft_external_id %s" % aircraft_external_id)
        else:
            log("LOOKUP got cached aircraft_external_id %s" % aircraft_external_id)

        flight.external_id = aircraft_external_id

    return flight.external_id

def bbox_start_change_cb(flight, flight_str):
    log("*** bbox_start_change_cb "+flight_str)
    t = Thread(target=bbox_change_cb, args=[flight, flight_str])
    t.start()

def bbox_change_cb(flight, flight_str):
    log("*** bbox_change_cb "+flight_str)

    flight.lock()
    flight_id = flight.tail
    flight_name = flight.flight_id.strip()
    if not flight_id:
        flight_id = flight_name
    scenic = False

    if "Pattern" in flight_str:
        flight.flags['scenic'] = True
    if "Landing" in flight_str:
        if 'scenic' in flight.flags:
            scenic = True
            flight.flags['scenic'] = False

    if not ("Landing" in flight_str or "Takeoff" in flight_str):
        flight.unlock()
        return

    aircraft_internal_id = lookup_or_create_aircraft(flight)

    if "Landing" in flight_str:
        log ("PUSHER adding landing")
        as_instance.add_op(aircraft_internal_id, flight.lastloc.now, scenic, "LANDING", flight_name)
    elif "Takeoff" in flight_str:
        log ("PUSHER adding takeoff")
        as_instance.add_op(aircraft_internal_id, flight.lastloc.now, scenic, "TAKEOFF", flight_name)
    flight.unlock()

class CPE:
    def __init__(self, flight1, flight2, latdist, altdist, create_time):
        if (flight1.flight_id > flight2.flight_id):
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

current_cpes = dict()
CPE_GC_TIME = 60
gc_thread = None
# CPE = Close Proximity Event
# push to server at first detection and when gc'ed

def cpe_start_cb(flight1, flight2, latdist, altdist):
    t = Thread(target=cpe_cb, args=[flight1, flight2, latdist, altdist])
    t.start()

def cpe_cb(flight1, flight2, latdist, altdist):
    global gc_thread
    if not gc_thread:
        gc_thread = Thread(target=gc_loop)
        gc_thread.start()

    dbg("CPE_CB " + flight1.flight_id + " " + flight2.flight_id)

    now = flight1.lastloc.now
    # always create a new CPE to get flight1/flight2 ordering right
    cpe = CPE(flight1, flight2, latdist, altdist, now)
    cpe.flight1.lock()
    cpe.flight2.lock()

    flight1_internal_id = lookup_or_create_aircraft(cpe.flight1)
    flight2_internal_id = lookup_or_create_aircraft(cpe.flight2)

    key = cpe.key()
    if key in current_cpes:
        dbg("CPE update " + key)
        current_cpes[key].update(latdist, altdist, now)
    else:
        dbg("CPE add " + key)
        cpe_id = as_instance.add_cpe(flight1_internal_id, flight2_internal_id,
            latdist, altdist, now)
        cpe.id = cpe_id
        current_cpes[key] = cpe

    cpe.flight2.unlock()
    cpe.flight1.unlock()

last_time_seen = 0

def gc_loop():
    while True:
        time.sleep(10)
        cpe_gc()

# XXX current_cpes race?
def cpe_gc():
    dbg("CPE_GC")

    for cpe in list(current_cpes.values()):
        dbg("CPE_GC %s %d %d" % (cpe.key(), time.time(), cpe.last_time))

        # using time.time() here won't work in replay cases, but we're not
        # replaying with this tool
        # XXX maybe should eval last_time inside lock?
        if time.time() - cpe.last_time > CPE_GC_TIME:
            dbg("CPE final update " + cpe.flight1.flight_id + " " + cpe.flight2.flight_id)

            cpe.flight1.lock()
            cpe.flight2.lock()
            dbg("CPE final update locked" + cpe.flight1.flight_id + " " + cpe.flight2.flight_id)

            flight1_internal_id = lookup_or_create_aircraft(cpe.flight1)
            flight2_internal_id = lookup_or_create_aircraft(cpe.flight2)
            as_instance.update_cpe(flight1_internal_id, flight2_internal_id,
                cpe.min_latdist, cpe.min_altdist, cpe.create_time, cpe.id)
            del current_cpes[cpe.key()]

            cpe.flight2.unlock()
            cpe.flight1.unlock()

def test_cb():
    t = Thread(target=test_cb_body)
    t.start()

def test_cb_body():
    dbg("TEST THREAD RUNNING")
    now = datetime.datetime.now()

    # set the timezone to Pacific Time
    pacific_tz = pytz.timezone('America/Los_Angeles')
    pacific_time = now.astimezone(pacific_tz)
    desc = "TEST AT %d/%d" % (pacific_time.day,pacific_time.hour)

    as_instance.add_aircraft("N123XXX", test=True, description=desc)


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
