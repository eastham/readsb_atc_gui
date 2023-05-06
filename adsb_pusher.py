# accept traffic from readsb and push relevant flights to
# an appsheet app.

import adsb_receiver
from dbg import dbg, set_dbg_level, log, ppdbg
from bboxes import Bboxes
from flight import Flight, Location
import appsheet_api
import datetime
import time

as_instance = appsheet_api.Appsheet()
flight_history_dict = dict()
flight_id_cache = dict()

def bbox_change_cb(flight, bbox_str):
    flight_id = flight.tail
    flight_name = flight.flight_id.strip()
    if not flight_id:
        flight_id = flight_name

    scenic = False

    if "Pattern" in bbox_str:
        flight_history_dict[flight_id] = True
    if "Landing" in bbox_str:
        if flight_id in flight_history_dict:
            scenic = True
            del flight_history_dict[flight_id]

    if not ("Landing" in bbox_str or "Takeoff" in bbox_str): return

    if flight_id in flight_id_cache:
        aircraft_internal_id = flight_id_cache[flight_id]
    else:
        aircraft_internal_id = as_instance.aircraft_lookup(flight_id)
        log("PUSHER got aircraft_internal_id %s" % aircraft_internal_id)
        if not aircraft_internal_id:
            aircraft_internal_id = as_instance.add_aircraft(flight_id)
            log("PUSHER now has aircraft_internal_id %s" % aircraft_internal_id)
        flight_id_cache[flight_id] = aircraft_internal_id

    optime = datetime.datetime.utcfromtimestamp(flight.lastloc.now)

    if "Landing" in bbox_str:
        log ("PUSHER adding landing")
        as_instance.add_op(aircraft_internal_id, optime, scenic, "LANDING", flight_name)
    elif "Takeoff" in bbox_str:
        log ("PUSHER adding takeoff")
        as_instance.add_op(aircraft_internal_id, optime, scenic, "TAKEOFF", flight_name)

class CPE:
    def __init__(self, flight1, flight2, latdist, altdist, time):
        if (flight1.flight_id > flight2.flight_id):
            self.flight2 = flight1
            self.flight1 = flight2
        else:
            self.flight1 = flight1
            self.flight2 = flight2
        self.latdist = self.min_latdist = latdist
        self.altdist = self.min_altdist = altdist
        self.create_time = self.last_time = time

    def update(self, latdist, altdist, time):
        self.latdist = latdist
        self.altdist = altdist
        self.last_time = time
        # perhaps this is better done with an absolute distance?
        if latdist <= self.min_latdist or altdist <= self.min_altdist:
            self.min_latdist = latdist
            self.min_altdist = altdist

    def key(self):
        key = "%s %s %s" % (self.flight1.flight_id.strip(),
            self.flight2.flight_id.strip(), self.create_time)


current_cpes = dict()
CPE_GC_TIME = 60

# CPE = Close Proximity Event
# push to server at first detection and when gc'ed
def cpe_cb(flight1, flight2, latdist, altdist):
    dbg("CPE_CB "+flight1.flight_id)
    time = flight1.lastloc.now
    cpe = CPE(flight1, flight2, latdist, altdist, time)

    if cpe.key() in current_cpes:
        current_cpes[key].update(latdist, altdist, time)
    else:
        as_instance.add_cpe(flight1, flight2, latdist, altdist, time)
        current_cpes[cpe.key()] = cpe


def cpe_gc(now):
    for cpe in current_cpes.values():
        if now - cpe.last_time > CPE_GC_TIME:
            as_instance.update_cpe(cpe.flight1, cpe.flight2, cpe.min_latdist,
                cpe.min_altdist, cpe.create_time)

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
    if args.test: tests_enable()

    bboxes_list = []
    for f in args.file:
        bboxes_list.append(Bboxes(f))

    listen = adsb_receiver.setup(args.ipaddr, args.port)

    adsb_receiver.flight_read_loop(listen, bboxes_list, None, None, cpe_cb, bbox_change_cb)
