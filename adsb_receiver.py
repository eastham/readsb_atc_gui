import dataclasses
import socket
import threading
import json
import signal
import time
from typing import Dict

from bboxes import Bboxes
from dbg import dbg, set_dbg_level, log, ppdbg
from flight import Flight, Location
from test import test_insert, tests_enable, run_test

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

        flight.update_inside_bboxes(self.bboxes, loc)

        if is_new_flight:
            if new_flight_cb: new_flight_cb(flight)
            if flight.in_any_bbox(): log("New flight: " + flight.to_str())
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
                if flight.in_any_bbox(): log("Expiring flight: %s" % f)
                if expire_cb: expire_cb(flight)
                del self.flight_dict[f]

        self.lock.release()

    def check_distance(self):
        """
        Check distance between all bbox'ed aircraft.
        O(n^2), can be expensive, but altitude and bbox limits help..
        """
        MIN_ALT_SEPARATION = 600
        MIN_DISTANCE = 1.   # nautical miles

        flight_list = list(self.flight_dict.values())

        for i, flight1 in enumerate(flight_list):
            if not flight1.in_any_bbox(): continue
            for j, flight2 in enumerate(flight_list[i+1:]):
                if not flight2.in_any_bbox(): continue
                loc1 = flight1.lastloc
                loc2 = flight2.lastloc
                if abs(loc1.alt_baro - loc2.alt_baro) < MIN_ALT_SEPARATION:
                    dist = loc1 - loc2
                    if dist < MIN_DISTANCE:
                        log("%s-%s inside minimum distance %.1f nm" %
                            (flight1.flight_id, flight2.flight_id, dist))


class TCPConnection:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        try:
            if self.sock: self.sock.close()     # reconnect case
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            print('Successful Connection')
        except:
            print('Connection Failed')
            raise

        self.f = self.sock.makefile()

    def readline(self):
        return self.f.readline()

def sigint_handler(signum, frame):
    exit(1)

def setup(ipaddr, port):
    print("Connecting to %s:%d" % (ipaddr, int(port)))

    signal.signal(signal.SIGINT, sigint_handler)
    listen = TCPConnection(ipaddr, int(port))
    listen.connect()

    dbg("Setup done")
    return listen

def flight_update_read(flights, listen, update_cb):

    try:
        line = listen.readline()
        jsondict = json.loads(line)
    except:
        print("Socket input/parse error, attempting to reconnect...")
        listen.connect()
        return
    # ppdbg(jsondict)

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

            flights.check_distance()

        run_test(lambda: test_insert(flights, update_cb))

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

    listen = setup(args.ipaddr, args.port)

    flight_read_loop(listen, bboxes_list, None, None)
