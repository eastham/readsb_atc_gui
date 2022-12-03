
# TODO
# probably need to expire out in-ram locations over an hour old...
# write to disk hourly, clear everything more than 5 min old

# makerow: return appropriate dict to add
import dataclasses
from dataclasses import dataclass, field
import socket
from typing import Optional
import threading
from kivy.clock import Clock
from functools import partial
import statistics
from dbg import dbg, test

EXPIRE_SECS = 15

@dataclass
class Location:
    """A single aircraft position"""
    lat: float
    lon: float
    alt_baro: int
    now: Optional[float]
    flight: str
    track: float = 0.

    def __post_init__(self):
        if type(self.alt_baro) is str: self.alt_baro = -1 # alt_baro can be "ground"
        now = time.time()

    @classmethod
    def from_dict(cl, d: dict):
        nd = {}
        for f in dataclasses.fields(Location):
            if f.name in d:
                nd[f.name] = d[f.name]
            else:
                nd[f.name] = "N/A"
        return Location(**nd)

    def __sub__(self, other):
        return Location(lat=self.lat - other.lat,
                        lon=self.lon - other.lon,
                        alt_baro=self.alt_baro - other.alt_baro,
                        now=self.now - other.now,
                        flight=self.flight)

    def __lt__(self, other):
        return self.alt_baro < other.alt_baro

    def __gt__(self, other):
        return self.alt_baro > other.alt_baro


class Locations:
    """per-second per-aircraft lat/long/alt/time/id

    probably need to expire out in-ram locations over an hour old...
    write to disk hourly, clear everything more than 5 min old
    """
    def __init__(self):
        #self.df = pd.DataFrame(columns=[f.name for f in dataclasses.fields(Location)])
        self.list = []

    def add_location(self, loc: Location):
        self.list.append(loc)

ALT_TRACK_ENTRIES = 5

@dataclass
class Flight:
    """Summary of a series of locations, plus other annotations"""
    flight: str
    firstloc: Location
    lastloc: Location
    bbox_index: int = -1
    notes: str = None
    code: int = -1
    pilot: str = None
    alt_list: list = field(default_factory=list)

    def track_alt(self, alt):
        avg = alt
        if len(self.alt_list):
            avg = statistics.fmean(self.alt_list)
        if len(self.alt_list) == ALT_TRACK_ENTRIES:
            self.alt_list.pop(0)
        self.alt_list.append(alt)

        avg = int(avg)
        if alt > avg: return 1
        if alt < avg: return -1
        return 0

class Flights:
    """generated from locations row with no more than 5 min break"""
    def __init__(self, bboxes):
        self.dict = {}      # dict of Flights
        self.bboxes = bboxes
        self.lock = threading.Lock()

    def add_location(self, loc: Location, gui_app):
        flightname = loc.flight
        if flightname == "N/A": return

        self.lock.acquire()

        if flightname in self.dict:
            flight = self.dict[flightname]
        else:
            # XXX seems to be creating multiple in N/A case
            flight = self.dict[flightname] = Flight(flightname, loc, loc)
            flight.firstloc = loc
            print("new flight %s " % flightname)

        bbox_index = self.bboxes.contains(loc.lat, loc.lon, loc.track, loc.alt_baro)

        if bbox_index >= 0:
            flight.bbox_index = bbox_index
            if gui_app:
                gui_app.update_strip(flight.flight, bbox_index)

        if flight.bbox_index >= 0:  # rendered
            altchange = flight.track_alt(loc.alt_baro)
            altchangestr = " "
            if altchange > 0:
                altchangestr = "^"
            if altchange < 0:
                altchangestr = "v"

            if gui_app: gui_app.update_strip_alt(flight.flight, altchangestr, loc.alt_baro)

        flight.lastloc = loc

        self.lock.release()

        return flight

    def expire_old(self, gui_app):
        self.lock.acquire()
        for f in list(self.dict):

            if (time.time() - self.dict[f].lastloc.now > EXPIRE_SECS):
                print("expiring flight %s" % f)
                if gui_app and self.dict[f].bbox_index >= 0:
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

import pprint
import socket
import json
import signal
import time
from bboxes import Bboxes

pp = pprint.PrettyPrinter(indent=4)

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
        #data = self.sock.recv(1024).decode("utf-8")
        data = self.f.readline()
        return data

bboxes = Bboxes("sjc.kml")
locations = Locations()
flights = Flights(bboxes)
gui_app = None


def abortcb(signum, frame):
    exit(1)

def setup():
    signal.signal(signal.SIGINT, abortcb)
    listen = TCPConnection()
    listen.connect('192.168.87.60',30666)
    lastupdate = 0
    dbg("AIO setup done")
    return listen

boot_time = time.time()
last_uptime = 0

def test_insert(flight):
    global last_uptime
    uptime = time.time() - boot_time

    if uptime > 5 and last_uptime < 5:
        dbg("--- Test update 1")
        flights.add_location(Location(flight="**test 1**", now=time.time(), track=0, alt_baro=1000, lat=37.395647,lon=-121.954186), gui_app)
        flights.add_location(Location(flight="**test 2**", now=time.time(), track=0, alt_baro=1000, lat=37.395647,lon=-121.954186), gui_app)

        flights.add_location(Location(flight="**test 1**", now=time.time(), track=0, alt_baro=1500, lat=36.395647,lon=-121.954186), gui_app)
        flights.add_location(Location(flight="**test 2**", now=time.time(), track=0, alt_baro=1600, lat=36.395647,lon=-121.954186), gui_app)
        pass

    if uptime > 10 and last_uptime < 10:
        dbg("--- Test update 2")
        flights.add_location(Location(flight="**test 1**", now=time.time(), track=0, alt_baro=1500, lat=36.395647,lon=-121.954186), gui_app)
        flights.add_location(Location(flight="**test 1**", now=time.time(), track=0, alt_baro=1600, lat=36.395647,lon=-121.954186), gui_app)
        flights.add_location(Location(flight="**test 2**", now=time.time(), track=0, alt_baro=1000, lat=37.395647,lon=-121.954186), gui_app)

    if uptime > 15 and last_uptime < 15:
        # PAO
        dbg("--- Test update 3")
        flights.add_location(Location(flight="**test 2**", now=time.time(), track=10, alt_baro=1000, lat=37.461671,lon=-122.121137), gui_app)

    last_uptime = uptime

def procline(listen, app):
    global gui_app
    gui_app = app
    line = listen.readline()
    # print(line)
    jsondict = json.loads(line)
    # pp.pprint(jsondict)

    loc = Location.from_dict(jsondict)
    locations.add_location(loc)
    flight = flights.add_location(loc, gui_app)

    test(lambda: test_insert(flight))

def expire_old_flights(gui_app):
    flights.expire_old(gui_app)


if __name__ == '__main__' :
    listen = setup()

    read_thread = threading.Thread(target=readline_loop, args=(listen,))
