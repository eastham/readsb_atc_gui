import dataclasses
from dataclasses import dataclass, field, InitVar
from typing import Optional
import time
import statistics
from dbg import dbg

@dataclass
class Location:
    """A single aircraft position + data update """
    lat: float = 0.
    lon: float = 0.
    alt_baro: int = 0
    now: Optional[float] = 0
    flight: Optional[str] = "N/A" # the flight id
    gs: Optional[float] = 0
    track: float = 0.

    @classmethod
    def from_dict(cl, d: dict):
        nd = {}
        for f in dataclasses.fields(Location):
            if f.name in d:
                nd[f.name] = d[f.name]

        return Location(**nd)

    def __sub__(self, other):
        return Location(lat=self.lat - other.lat,
                        lon=self.lon - other.lon,
                        alt_baro=self.alt_baro - other.alt_baro,
                        now=self.now - other.now)

    def __lt__(self, other):
        return self.alt_baro < other.alt_baro

    def __gt__(self, other):
        return self.alt_baro > other.alt_baro

@dataclass
class Flight:
    """Summary of a series of locations, plus other annotations"""
    flight_id: str
    firstloc: Location
    lastloc: Location
    bbox_list: InitVar[list]
    alt_list: list = field(default_factory=list)  # last n altitudes we've seen
    inside_bboxes: list = field(default_factory=list)  # most recent bboxes we've been inside, by file
    ALT_TRACK_ENTRIES = 5

    def __post_init__(self, bbox_list):
        self.inside_bboxes = [-1] * len(bbox_list)

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

    def update_inside_bboxes(self, bbox_list, loc):
        for i, bbox in enumerate(bbox_list):
            new_bbox = bbox_list[i].contains(loc.lat, loc.lon, loc.track, loc.alt_baro)
            if self.inside_bboxes[i] != new_bbox:
                dbg("Flight.update_inside_bboxes: %s now inside %s" % (self.flight_id, bbox_list[i].boxes[new_bbox].name))
                self.inside_bboxes[i] = new_bbox

    def get_bbox_at_level(self, level, bboxes_list):
        inside_n = self.inside_bboxes[level]
        if inside_n >= 0:
            bboxes = bboxes_list[level]
            return bboxes.boxes[inside_n]
        else:
            return None
