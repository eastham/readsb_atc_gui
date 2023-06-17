import socket
import threading
import json
import signal
import datetime
import sys
from typing import Dict

from test import test_insert, tests_enable, run_test
from bboxes import Bboxes
from dbg import dbg, set_dbg_level, log
from flight import Flight, Location

class Flights:
    """all Flight objects in the system, indexed by flight_id"""
    flight_dict: Dict[str, Flight] = {}
    lock: threading.Lock = threading.Lock()
    EXPIRE_SECS: int = 60

    def __init__(self, bboxes):
        self.bboxes = bboxes

    def add_location(self, loc: Location, new_flight_cb, update_flight_cb, bbox_change_cb):
        """
        Track an aircraft location update, update what bounding boxes it's in,
        and fire callbacks to update the gui or do user-defined tasks.

        loc: Location/flight info to update
        new_flight_cb(flight): called if loc is a new flight and just added to the database.
        update_flight_cb(flight): called when a flight position is updated.
        """

        flight_id = loc.flight
        # XXX do we always convert from icao?  have seen some aircraft with
        # empty string for flight_id
        if not flight_id or flight_id == "N/A": return loc.now

        self.lock.acquire() # lock needed since testing can race

        if flight_id in self.flight_dict:
            is_new_flight = False
            flight = self.flight_dict[flight_id]
            flight.update_loc(loc)
        else:
            is_new_flight = True
            flight = self.flight_dict[flight_id] = Flight(flight_id, loc.tail, loc, loc, self.bboxes)

        flight.update_inside_bboxes(self.bboxes, loc, bbox_change_cb)

        if is_new_flight:
            if new_flight_cb: new_flight_cb(flight)
            if flight.in_any_bbox(): log("New flight: " + flight.to_str())
        else:
            #if flight.in_any_bbox():
            #    logline = "Updating flight: " + flight.to_str()
            #    dbg(logline)
            if update_flight_cb: update_flight_cb(flight)

        self.lock.release()
        return flight.lastloc.now

    def expire_old(self, expire_cb, last_read_time):
        self.lock.acquire()
        for f in list(self.flight_dict):
            flight = self.flight_dict[f]
            if last_read_time - flight.lastloc.now > self.EXPIRE_SECS:
                if flight.in_any_bbox(): log("Expiring flight: %s" % f)
                if expire_cb: expire_cb(flight)
                del self.flight_dict[f]

        self.lock.release()

    def check_distance(self, annotate_cb, last_read_time):
        """
        Check distance between all bbox'ed aircraft.
        O(n^2), can be expensive, but altitude and bbox limits help..
        """
        dbg("check_distance")
        MIN_ALT_SEPARATION = 400 # 8000 # 400
        MIN_ALT = 4000 # 100 # 4000
        MIN_DISTANCE = .3 # 1   # .3 # nautical miles 
        MIN_FRESH = 10 # seconds, otherwise not evaluated
        flight_list = list(self.flight_dict.values())

        for i, flight1 in enumerate(flight_list):
            if not flight1.in_any_bbox(): continue
            if last_read_time - flight1.lastloc.now > MIN_FRESH: continue
            for j, flight2 in enumerate(flight_list[i+1:]):
                if not flight2.in_any_bbox(): continue
                if last_read_time - flight2.lastloc.now > MIN_FRESH: continue

                loc1 = flight1.lastloc
                loc2 = flight2.lastloc
                if (loc1.alt_baro < MIN_ALT or loc2.alt_baro < MIN_ALT): continue
                if abs(loc1.alt_baro - loc2.alt_baro) < MIN_ALT_SEPARATION:
                    dist = loc1 - loc2

                    if dist < MIN_DISTANCE:
                        print("%s-%s inside minimum distance %.1f nm" %
                            (flight1.flight_id, flight2.flight_id, dist))
                        print("LAT, %f, %f, %d" % (flight1.lastloc.lat, flight1.lastloc.lon, last_read_time))
                        if annotate_cb:

                            annotate_cb(flight1, flight2, dist, abs(loc1.alt_baro - loc2.alt_baro))
                            annotate_cb(flight2, flight1, dist, abs(loc1.alt_baro - loc2.alt_baro))


class TCPConnection:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None
        self.f = None

    def connect(self):
        try:
            if self.sock: self.sock.close()     # reconnect case
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            print('Successful Connection')
        except Exception:
            print('Connection Failed')
            raise

        self.f = self.sock.makefile()

    def readline(self):
        return self.f.readline()

def sigint_handler(signum, frame):
    sys.exit(1)

def setup(ipaddr, port):
    print("Connecting to %s:%d" % (ipaddr, int(port)))

    signal.signal(signal.SIGINT, sigint_handler)
    conn = TCPConnection(ipaddr, int(port))
    conn.connect()

    dbg("Setup done")
    return conn

def flight_update_read(flights, listen, update_cb, bbox_change_cb):
    try:
        line = listen.readline()
        jsondict = json.loads(line)
    except Exception:
        print("Socket input/parse error, attempting to reconnect...")
        listen.connect()
        return
    #ppdbg(jsondict)

    loc_update = Location.from_dict(jsondict)
    last_ts = flights.add_location(loc_update, update_cb, update_cb, bbox_change_cb)
    return last_ts

def flight_read_loop(listen, bbox_list, update_cb, expire_cb, annotate_cb, bbox_change_cb, test_cb=None):
    CHECKPOINT_INTERVAL = 10 # seconds
    last_checkpoint = 0
    TEST_INTERVAL = 60*60 # run test every this many seconds
    last_test = 0
    flights = Flights(bbox_list)

    while True:
        last_read_time = flight_update_read(flights, listen, update_cb, bbox_change_cb)
        if not last_checkpoint: last_checkpoint = last_read_time

        # XXX this skips during gaps when no aircraft are seen
        if last_read_time and last_read_time - last_checkpoint >= CHECKPOINT_INTERVAL:
            datestr = datetime.datetime.utcfromtimestamp(last_read_time).strftime('%Y-%m-%d %H:%M:%S')
            print("Checkpoint: %d %s" % (last_read_time, datestr))

            flights.expire_old(expire_cb, last_read_time)
            flights.check_distance(annotate_cb, last_read_time)
            last_checkpoint = last_read_time

        if test_cb and last_read_time and last_read_time - last_test >= TEST_INTERVAL:
            test_cb()
            last_test = last_read_time

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

    flight_read_loop(listen, bboxes_list, None, None, None, None)
