#!/usr/bin/python3

from fastkml import kml
from shapely.geometry import Point, LineString, Polygon
import pprint
import re
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
    index: int  # index in bboxes.  needed to know what dialog box to dr


class Bboxes:
    def __init__(self, fn):
        self.boxes = []    # list of Bbox'es

        with open(fn, 'rt', encoding="utf-8") as myfile:
          doc = myfile.read()
        k = kml.KML()
        k.from_string(doc.encode('utf-8'))
        features = list(k.features())
        self.parse_placemarks(features)

    def parse_placemarks(self, document):
        polygon_ctr = 0
        for feature in document:
          if isinstance(feature, kml.Placemark):
            #print("got placemark " + feature.to_string())
            #print("got placemark " + feature.name)
            re_result = re.search(r"([\w\d\s]+):\s*(\d+)-(\d+) (\d+)-(\d+)", feature.name)
            if not re_result: raise ValueError("kml parse error: " + feature.name)
            name = re_result.group(1)
            minalt = int(re_result.group(2))
            maxalt = int(re_result.group(3))
            starthdg = int(re_result.group(4))
            endhdg = int(re_result.group(5))

            print("Using Bounding Box %s: %d-%d" % (name,minalt,maxalt))
            newbox = Bbox(polygon=Polygon(feature.geometry),
                minalt=minalt, maxalt=maxalt, starthdg=starthdg,
                endhdg=endhdg, name=name, index=polygon_ctr)
            polygon_ctr += 1
            print(pp.pprint(newbox))
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
            dbg("hdg %d %d-%d" %(hdg,start,end))
            exit(1)

    def contains(self, lat, long, hdg, alt):
        "returns index of first matching bounding box, otherwise -1 if not found"
        for i, box in enumerate(self.boxes):
            # print(pp.pprint(box))
            if box.polygon.contains(Point(long,lat)) and self.hdg_contains(hdg, box.starthdg, box.endhdg):
                if (alt > box.minalt and alt < box.maxalt):
                    return i
        return -1
        # XXX alt not handled yet
