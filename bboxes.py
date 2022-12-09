#!/usr/bin/python3

import pprint
import re
from fastkml import kml
from shapely.geometry import Point, LineString, Polygon
from dataclasses import dataclass
from dbg import dbg

pp = pprint.PrettyPrinter(indent=4)

@dataclass
class Bbox:
    polygon: Polygon
    minalt: int
    maxalt: int
    starthdg: int
    endhdg: int
    name: str

class Bboxes:
    def __init__(self, fn):
        self.boxes = []    # list of Bbox objects

        with open(fn, 'rt', encoding="utf-8") as myfile:
          doc = myfile.read()
        k = kml.KML()
        k.from_string(doc.encode('utf-8'))
        features = list(k.features())
        self.parse_placemarks(features)

    def parse_placemarks(self, document):
        for feature in document:
          if isinstance(feature, kml.Placemark):
            re_result = re.search(r"^([^:]+):\s*(\d+)-(\d+) (\d+)-(\d+)",
                feature.name)
            if not re_result:
                raise ValueError("KML feature name parse error: " +
                    feature.name)
            name = re_result.group(1)
            minalt = int(re_result.group(2))
            maxalt = int(re_result.group(3))
            starthdg = int(re_result.group(4))
            endhdg = int(re_result.group(5))

            dbg("Adding bounding box %s: %d-%d %d-%d deg" %
                (name,minalt,maxalt,starthdg,endhdg))
            newbox = Bbox(polygon=Polygon(feature.geometry),
                minalt=minalt, maxalt=maxalt, starthdg=starthdg,
                endhdg=endhdg, name=name)
            self.boxes.append(newbox)
        for feature in document:
          if isinstance(feature, kml.Folder):
              self.parse_placemarks(list(feature.features()))
          if isinstance(feature, kml.Document):
              self.parse_placemarks(list(feature.features()))

    def hdg_contains(self, hdg, start, end):
        try:
            if end < start:
                return hdg >= start or hdg <= end
            return hdg >= start and hdg <= end
        except:
            exit(1)

    def contains(self, lat, long, hdg, alt):
        "returns index of first matching bounding box, or -1 if not found"
        for i, box in enumerate(self.boxes):
            if (box.polygon.contains(Point(long,lat)) and
                self.hdg_contains(hdg, box.starthdg, box.endhdg)):
                if (alt > box.minalt and alt < box.maxalt):
                    return i
        return -1
