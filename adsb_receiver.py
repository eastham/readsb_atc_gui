
import dataclasses
import socket
import threading
from functools import partial
import pprint
import json
import signal
import time
from typing import Dict

from bboxes import Bboxes
from dbg import dbg, run_test, set_dbg_level
from flight import Flight, Location
from test import test_insert

pp = pprint.PrettyPrinter(indent=4)

class Flights:
    """all Flight objects in the system, indexed by flight_id"""
    flight_dict: Dict[str, Flight] = {}
    lock: threading.Lock = threading.Lock()
    EXPIRE_SECS: int = 15

    def __init__(self, bboxes):
        self.bboxes = bboxes

    def add_location(self, loc: Location, new_flight_cb, update_flight_cb):
        """
        Track an aircraft location update, update what bounding boxes it's in,
        and fire callbacks to update the gui or do user-defined tasks.

        loc: Location/flight info to update
        new_flight_cb(flight): called if loc is a new flight and just added to the database.
        update_flight_cb(flight): called when a flight position is updated.
        """
        flight_id = loc.flight
        if flight_id == "N/A": return

        self.lock.acquire()

        if flight_id in self.flight_dict:
            is_new_flight = False
            flight = self.flight_dict[flight_id]
            flight.lastloc = loc
        else:
            is_new_flight = True
            flight = self.flight_dict[flight_id] = Flight(flight_id, loc, loc, self.bboxes)

        if is_new_flight:
            logline = "Saw new flight: " + flight.to_str()
            dbg(logline)

        flight.update_inside_bboxes(self.bboxes, loc)

        if is_new_flight:
            if new_flight_cb: new_flight_cb(flight)
        else:
            #if flight.in_any_bbox():
            #    logline = "Updating flight: " + flight.to_str()
            #    dbg(logline)
            if update_flight_cb: update_flight_cb(flight)

        self.lock.release()

        return flight

    def expire_old(self, expire_cb):
        self.lock.acquire()
        for f in list(self.flight_dict):
            flight = self.flight_dict[f]
            if (time.time() - flight.lastloc.now > self.EXPIRE_SECS):
                dbg("Expiring flight: %s" % f)
                if expire_cb: expire_cb(flight)
                del self.flight_dict[f]

        self.lock.release()

    def dump(self):
        self.lock.acquire()
        for f, fl in self.flight_dict.items():
            dbg("%s: seen for %d sec type %s" % (fl.flight_id,
                            (fl.lastloc-fl.firstloc).now, fl.bbox_index))
        self.lock.release()

class TCPConnection:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self, host, port):
        try:
            self.sock.connect((host, port))
            print('Successful Connection')
        except:
            print('Connection Failed')

        self.f = self.sock.makefile()

    def readline(self):
        return self.f.readline()

def sigint_handler(signum, frame):
    exit(1)

def setup(ipaddr, port):
    print("Connecting to %s:%d" % (ipaddr, int(port)))

    signal.signal(signal.SIGINT, sigint_handler)
    listen = TCPConnection()
    listen.connect(ipaddr, int(port))

    dbg("Setup done")
    return listen

def flight_update_read(flights, listen, update_cb):
    line = listen.readline()

    jsondict = json.loads(line)
    # pp.pprint(jsondict)

    loc_update = Location.from_dict(jsondict)
    flight = flights.add_location(loc_update, update_cb, update_cb)

def flight_read_loop(listen, bbox_list, update_cb, expire_cb): # need two callbacks, one to add one to remove
    last_expire = time.time()
    flights = Flights(bbox_list)

    while True:
        flight_update_read(flights, listen, update_cb)

        if time.time() - last_expire > 1:
            flights.expire_old(expire_cb)
            last_expire = time.time()

        run_test(lambda: test_insert(flights, update_cb))

if __name__ == "__main__":
    # No-GUI mode, see controller.py for GUI
    import argparse

    parser = argparse.ArgumentParser(description="match flights against kml bounding boxes")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument('file', nargs='+', help="kml files to use")
    parser.add_argument('--ipaddr', help="IP address to connect to", required=True)
    parser.add_argument('--port', help="port to connect to", required=True)
    args = parser.parse_args()

    if args.verbose: set_dbg_level(True)

    bboxes_list = []
    for f in args.file:
        bboxes_list.append(Bboxes(f))

    listen = setup(args.ipaddr, args.port)

    flight_read_loop(listen, bboxes_list, None, None)
