import dataclasses
from dataclasses import dataclass, field
from typing import Optional
import time
import statistics

@dataclass
class Location:
    """A single aircraft position update"""
    lat: float
    lon: float
    alt_baro: int
    now: Optional[float]
    flight: str
    gs: Optional[float]
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

@dataclass
class Flight:
    """Summary of a series of locations, plus other annotations"""
    flight: str
    firstloc: Location
    lastloc: Location
    bbox_index: int = -1
    alt_list: list = field(default_factory=list)

    ALT_TRACK_ENTRIES = 5

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
