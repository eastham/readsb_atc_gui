import dataclasses
from dataclasses import dataclass, field, InitVar
from typing import Optional
import time
import statistics
import collections
import typing
import datetime
import threading

from geopy import distance
import bboxes
from dbg import dbg, log
from icao_nnumber_converter_us import n_to_icao, icao_to_n
from threading import Lock

@dataclass
class Location:
    """A single aircraft position + data update """
    lat: float = 0.
    lon: float = 0.
    alt_baro: int = 0
    now: Optional[float] = 0
    flight: Optional[str] = "N/A" # the flight id
    hex: Optional[str] = None   # ICAO code
    tail: Optional[str] = None # N-number from ICAO code
    gs: Optional[float] = 0
    track: float = 0.

    def __post_init__(self):
        """sometimes these values come in as strings when not available"""
        if not isinstance(self.lat, float): self.lat = 0
        if not isinstance(self.lon, float): self.lon = 0
        if not isinstance(self.alt_baro, int): self.alt_baro = 0
        if not isinstance(self.gs, int): self.gs = 0
        if not isinstance(self.track, float): self.track = 0.

    @classmethod
    def from_dict(cl, d: dict):
        nd = {}
        for f in dataclasses.fields(Location):
            if f.name in d:
                nd[f.name] = d[f.name]
        # XXX should this be in flight?
        if "hex" in d:
            tail = icao_to_n(d["hex"])
            if tail: nd["tail"] = tail

        return Location(**nd)

    def to_str(self):
        s = "%s: %d MSL %d deg %.4f, %.4f" % (self.flight, self.alt_baro,
            self.track, self.lat, self.lon)
        return s

    def __sub__(self, other):
        """Return distance between two Locations in nm"""
        return distance.distance((self.lat, self.lon), (other.lat, other.lon)).nm

    def __lt__(self, other):
        return self.alt_baro < other.alt_baro

    def __gt__(self, other):
        return self.alt_baro > other.alt_baro

@dataclass
class Flight:
    """Summary of a series of locations, plus other annotations"""
    # Caution when changing: ctor positional args implied
    flight_id: str  # n number if not flight id
    tail: str       # can be none
    firstloc: Location
    lastloc: Location
    bboxes_list: list = field(default_factory=list)
    external_id: str = None # optional, database id for this flight
    alt_list: list = field(default_factory=list)  # last n altitudes we've seen
    inside_bboxes: list = field(default_factory=list)  # most recent bboxes we've been inside, by file
    threadlock: Lock = field(default_factory=Lock)
    flags: dict = field(default_factory=lambda: ({}))
    ALT_TRACK_ENTRIES = 5

    def __post_init__(self):
        self.inside_bboxes = [-1] * len(self.bboxes_list)

    def to_str(self):
        string = self.lastloc.to_str()
        bbox_name_list = []
        for i, bboxes in enumerate(self.bboxes_list):
            bboxes_index = self.inside_bboxes[i]
            if bboxes_index >= 0:
                bbox_name_list.append(bboxes.boxes[bboxes_index].name)
            else:
                bbox_name_list.append(" ")
        string += " " + str(bbox_name_list)
        return string

    def lock(self):
        self.threadlock.acquire()

    def unlock(self):
        self.threadlock.release()

    def in_any_bbox(self):
        for index in self.inside_bboxes:
            if index >= 0: return True
        return False

    def track_alt(self, alt):
        avg = alt
        if len(self.alt_list):
            avg = statistics.fmean(self.alt_list)
        if len(self.alt_list) == self.ALT_TRACK_ENTRIES:
            self.alt_list.pop(0)
        self.alt_list.append(alt)

        avg = int(avg)
        if alt > avg: return 1
        if alt < avg: return -1
        return 0

    def get_alt_change_str(self, alt):
        altchange = self.track_alt(alt)
        altchangestr = "  "
        if altchange > 0:
            altchangestr = "^"
        if altchange < 0:
            altchangestr = "v"
        return altchangestr

    def update_loc(self, loc):
        self.lastloc = loc

    def update_inside_bboxes(self, bbox_list, loc, change_cb):
        changes = False
        for i, bbox in enumerate(bbox_list):
            new_bbox = bbox_list[i].contains(loc.lat, loc.lon, loc.track, loc.alt_baro)
            if self.inside_bboxes[i] != new_bbox:
                changes = True
                self.inside_bboxes[i] = new_bbox

        if changes:
            flighttime = datetime.datetime.fromtimestamp(self.lastloc.now)
            dt = datetime.datetime.today()
            tail = self.tail if self.tail else "(unk)"
            log(tail + " Flight bbox change at " + flighttime.strftime("%H:%M") +
                ": " + self.to_str())
            if change_cb: change_cb(self, self.to_str())

    def get_bbox_at_level(self, level, bboxes_list):
        inside_n = self.inside_bboxes[level]
        if inside_n >= 0:
            bboxes = bboxes_list[level]
            return bboxes.boxes[inside_n]
        else:
            return None
