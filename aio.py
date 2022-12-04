
# TODO
# probably need to expire out in-ram locations over an hour old...
# write to disk hourly, clear everything more than 5 min old

import dataclasses
import socket
import threading
from kivy.clock import Clock
from functools import partial
import pprint
import json
import signal
import time

from bboxes import Bboxes
from dbg import dbg, test
from flight import Flight, Location

pp = pprint.PrettyPrinter(indent=4)

class Flights:
    """generated from locations row with no more than 5 min break"""
    def __init__(self, bboxes):
        self.dict = {}      # dict of Flight by flight id
        self.bboxes = bboxes
        self.lock = threading.Lock()
        self.EXPIRE_SECS = 15

    def add_location(self, loc: Location, gui_app):
        flightname = loc.flight
        if flightname == "N/A": return

        self.lock.acquire()

        if flightname in self.dict:
            flight = self.dict[flightname]
        else:
            flight = self.dict[flightname] = Flight(flightname, loc, loc)
            flight.firstloc = loc
            print("new flight %s " % flightname)

        bbox_index = self.bboxes.contains(loc.lat, loc.lon, loc.track, loc.alt_baro)
        flight.bbox_index = bbox_index

        if gui_app:
            gui_app.update_strip(flight.flight, bbox_index)
            altchangestr = flight.get_alt_change_str(loc.alt_baro)
            gui_app.update_strip_alt(flight.flight, altchangestr, loc.alt_baro, loc.gs)

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
            print("%s: seen for %d sec type %s" % (fl.flight,
                            (fl.lastloc-fl.firstloc).now, fl.bbox_index))
        self.lock.release()

    def getmatrix(self):
        self.lock.acquire()

        matrix = []
        for f, fl in self.dict.items():
            matrix.append([fl.flight, fl.bbox_index, fl.lastloc.now])
        self.lock.release()

        return matrix



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

boot_time = time.time()
last_test_uptime = 0

def test_insert(flights, app):
    global last_test_uptime
    uptime = time.time() - boot_time

    if uptime >= 5 and last_test_uptime < 5:
        dbg("--- Test update 1")
        flights.add_location(Location(flight="**test 1**", now=time.time(), track=0, gs=100, alt_baro=1000, lat=37.395647,lon=-121.954186), app)
        flights.add_location(Location(flight="**test 2**", now=time.time(), track=0, gs=100, alt_baro=1000, lat=37.395647,lon=-121.954186), app)
        # default zone
        flights.add_location(Location(flight="**test 1**", now=time.time(), track=0, gs=100, alt_baro=1500, lat=37.434824,lon=-122.185409), app)
        # off map
        flights.add_location(Location(flight="**test 2**", now=time.time(), track=0, gs=100, alt_baro=10600, lat=36.395647,lon=-121.954186), app)
        pass

    if uptime >= 10 and last_test_uptime < 10:
        dbg("--- Test update 2")
        flights.add_location(Location(flight="**test 1**", now=time.time(), track=0, gs=100, alt_baro=1500, lat=36.395647,lon=-121.954186), app)
        flights.add_location(Location(flight="**test 1**", now=time.time(), track=0, gs=100, alt_baro=1600, lat=36.395647,lon=-121.954186), app)
        flights.add_location(Location(flight="**test 2**", now=time.time(), track=0, gs=100, alt_baro=1000, lat=37.395647,lon=-121.954186), app)

    if uptime >= 15 and last_test_uptime < 15:
        # PAO
        dbg("--- Test update 3")
        flights.add_location(Location(flight="**test 2**", now=time.time(), track=0, gs=100, alt_baro=1000, lat=37.461671,lon=-122.121137), app)

    last_test_uptime = uptime


def setup():
    signal.signal(signal.SIGINT, abortcb)
    listen = TCPConnection()
    listen.connect('192.168.87.60',30666)
    lastupdate = 0
    dbg("AIO setup done")
    return listen

def sock_read(flights, listen, app):
    line = listen.readline()
    # print(line)
    jsondict = json.loads(line)
    # pp.pprint(jsondict)

    loc = Location.from_dict(jsondict)
    flight = flights.add_location(loc, app)

    test(lambda: test_insert(flights, app))


def sock_read_loop(listen, controllerapp):
    last_expire = time.time()
    bboxes = Bboxes("sjc.kml")
    flights = Flights(bboxes)

    while True:
        sock_read(flights, listen, controllerapp)
        if time.time() - last_expire > 1:
            expire_old_flights(flights, controllerapp)
            last_expire = time.time()


def expire_old_flights(flights, app):
    flights.expire_old(app)
