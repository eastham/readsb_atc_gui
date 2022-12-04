
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
    """generated from locations row with no more than 5 min break"""
    def __init__(self, bboxes):
        self.dict = {}      # dict of Flight by flight id
        self.bboxes = bboxes
        self.lock = threading.Lock()
        self.EXPIRE_SECS = 15

    def add_location(self, loc: Location, gui_app):
        flight_id = loc.flight
        if flight_id == "N/A": return

        self.lock.acquire()

        if flight_id in self.dict:
            flight = self.dict[flight_id]
        else:
            flight = self.dict[flight_id] = Flight(flight_id, loc, loc, self.bboxes)
            flight.firstloc = loc
            print("new flight %s " % flight_id)

        flight.update_inside_bboxes(self.bboxes, loc)
        flight.bbox_index = flight.inside_bboxes[0] # XXX hack

        if gui_app:
            # XXX just pass in flight to callback registered earlier
            gui_app.update_strip(flight.flight_id, flight.bbox_index)
            altchangestr = flight.get_alt_change_str(loc.alt_baro)
            gui_app.update_strip_alt(flight.flight_id, altchangestr, loc.alt_baro, loc.gs)
            gui_app.update_strip_loc_string(flight, self.bboxes)
        flight.lastloc = loc
        self.lock.release()

        return flight

    def expire_old(self, gui_app):
        self.lock.acquire()
        for f in list(self.dict):
            if (time.time() - self.dict[f].lastloc.now > self.EXPIRE_SECS):
                print("expiring flight %s" % f)
                if gui_app:
                    gui_app.remove_strip(f, self.dict[f].bbox_index)
                del self.dict[f]

        self.lock.release()

    def dump(self):
        self.lock.acquire()
        for f, fl in self.dict.items():
            print("%s: seen for %d sec type %s" % (fl.flight_id,
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


def abortcb(signum, frame):
    exit(1)


def setup(ipaddr, port):
    dbg("Connecting to %s:%d" % (ipaddr,int(port)))
    signal.signal(signal.SIGINT, abortcb)
    listen = TCPConnection()
    listen.connect(ipaddr, int(port)) # '192.168.87.60',30666)
    lastupdate = 0
    dbg("Setup done")
    return listen

def flight_update_read(flights, listen, app):
    line = listen.readline()
    # print(line)
    jsondict = json.loads(line)
    # pp.pprint(jsondict)

    loc_update = Location.from_dict(jsondict)
    flight = flights.add_location(loc_update, app)

def flight_read_loop(listen, controllerapp, bbox_list): # need two callbacks, one to add one to remove
    last_expire = time.time()
    flights = Flights(bbox_list)

    while True:
        flight_update_read(flights, listen, controllerapp)
        if time.time() - last_expire > 1:
            flights.expire_old(controllerapp)
            last_expire = time.time()
        test(lambda: test_insert(flights, controllerapp))

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
    flight_read_loop(listen, None, bboxes_list)
