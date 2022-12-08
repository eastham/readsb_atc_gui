
# TODO
# probably need to expire out in-ram locations over an hour old...
# write to disk hourly, clear everything more than 5 min old

import dataclasses
import socket
import threading
from functools import partial
import pprint
import json
import signal
import time

from bboxes import Bboxes
from dbg import dbg, test, set_dbg_level
from flight import Flight, Location
from test import test_insert

pp = pprint.PrettyPrinter(indent=4)

class Flights:
    """all Flight objects in the system, indexed by flight_id"""
    def __init__(self, bboxes):
        self.dict = {}      # dict of Flight by flight id
        self.bboxes = bboxes
        self.lock = threading.Lock()
        self.EXPIRE_SECS = 15

    def add_location(self, loc: Location, new_flight_cb, update_flight_cb):
        """
        Track an aircraft location update, update what bounding boxes it's in,
        and fire callbacks to update the gui or do user-defined tasks.

        loc: Location/flight info to update
        new_flight_cb(flight): called if loc is a new flight and just added to the database.
        update_flight_cb(flight): called when the position of loc is updated.
        """
        flight_id = loc.flight
        if flight_id == "N/A": return

        self.lock.acquire()

        if flight_id in self.dict:
            is_new_flight = False
            flight = self.dict[flight_id]
            flight.lastloc = loc
        else:
            is_new_flight = True
            flight = self.dict[flight_id] = Flight(flight_id, loc, loc, self.bboxes)
            dbg("new flight %s " % flight_id)

        flight.update_inside_bboxes(self.bboxes, loc)

        if is_new_flight and new_flight_cb:
            new_flight_cb(flight)
        elif update_flight_cb:
            update_flight_cb(flight)

        self.lock.release()

        return flight

    def expire_old(self, expire_cb):
        self.lock.acquire()
        for f in list(self.dict):
            flight = self.dict[f]
            if (time.time() - flight.lastloc.now > self.EXPIRE_SECS):
                dbg("expiring flight %s" % f)
                if expire_cb: expire_cb(flight)
                del self.dict[f]

        self.lock.release()

    def dump(self):
        self.lock.acquire()
        for f, fl in self.dict.items():
            dbg("%s: seen for %d sec type %s" % (fl.flight_id,
                            (fl.lastloc-fl.firstloc).now, fl.bbox_index))
        self.lock.release()

class TCPConnection:
    def __init__(self, sock=None):
        if sock is None:
            self.sock = socket.socket(
                            socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock

    def connect(self, host, port):
        try:
            self.sock.connect((host, port))
            print('Successful Connection')
        except:
            print('Connection Failed')

        self.f = self.sock.makefile()

    def readline(self):
        data = self.f.readline()
        return data

def sigint_handler(signum, frame):
    exit(1)

def setup(ipaddr, port):
    print("Connecting to %s:%d" % (ipaddr,int(port)))
    signal.signal(signal.SIGINT, sigint_handler)
    listen = TCPConnection()
    listen.connect(ipaddr, int(port)) # '192.168.87.60',30666)
    lastupdate = 0
    dbg("Setup done")
    return listen

def flight_update_read(flights, listen, update_cb):
    line = listen.readline()
    # print(line)
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
        test(lambda: test_insert(flights, update_cb))

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="match flights against kml bounding boxes")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument('file', nargs='+', help="kml files to use")
    parser.add_argument('--ipaddr', help="IP address to connect to", required=True)
    parser.add_argument('--port', help="port to connect to", required=True)
    args = parser.parse_args()

    bboxes_list = []
    if args.verbose: set_dbg_level(True)
    for f in args.file:
        bboxes_list.append(Bboxes(f))

    listen = setup(args.ipaddr, args.port)
    flight_read_loop(listen, bboxes_list, None, None)