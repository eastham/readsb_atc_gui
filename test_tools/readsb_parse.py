#!/usr/bin/python3

import os
import gzip
import json
import pprint
import sys
from icao_nnumber_converter_us import n_to_icao, icao_to_n

from datetime import datetime, timedelta

ALTTHRESH = 4100    # passing thru this alt is considered a takeoff or landing
TIMEGAPTHRESH = 5   # wait this long after a landing before detecting a takeoff
IGNOREABOVE = 20000 # ignore aircraft above this alt, don't attempt to parse

# airport hours (date ignored)
open_datetime = datetime(2009, 12, 2, 6, 00)
close_datetime = datetime(2009, 12, 2, 18, 30)
scenicopen_datetime = datetime(2009, 12, 2, 6, 00)
scenicclose_datetime = datetime(2009, 12, 2, 8, 00)

allpoints = {}      # list of location dicts, indexed by timestamp
pp = pprint.PrettyPrinter(indent=4)

def timestr(ts):
    return (datetime.fromtimestamp(ts)).strftime('%H:%M:%S')

def datestr(ts):
    return (datetime.fromtimestamp(ts)).strftime('%Y-%m-%d')

def dump_allpoints():
    pp.pprint(allpoints)

# analyze a single tar1090 json file, which contains a handful of aircraft's
# traces for the day.
def analyze(d, tp_callback=None):
    #pp.pprint(d)
    global allpoints
    icao_num = d['icao']
    n_number = icao_to_n(icao_num)
    airborne = False
    first = True
    tail = None
    prev_land_datetime = datetime(2009, 12, 2, 6, 00)
    start_ts = int(d['timestamp'])
    output_json = []    # for importing to cesium or other visualizers

    # go through trace points for this aircraft
    for tp in d['trace']:
        time_offset = tp[0]
        lat = tp[1]
        long = tp[2]
        alt = tp[3]
        gs = int(tp[4]) if tp[4] else 0
        track = tp[5]
        flightdict = tp[8]  # flight metadata, occasionally contains tail number

        try:
            altint = int(alt)
        except Exception:
            if alt is None:
                alt = "0"
                altint = 0
            elif 'ground' in alt:
                alt = "0"
                altint = 0

        if altint > IGNOREABOVE: continue
        #print("|| %s ||" % tp)

        # per-tracepoint timestamp is seconds past the per-file timestamp
        this_ts = start_ts+int(tp[0])
        this_datetime = datetime.fromtimestamp(this_ts)

        if not tail and flightdict is not None and 'flight' in flightdict:
            tail = flightdict['flight'].strip()
            #print("found tail # " + tail)

        # add this location to allpoints
        newdict = {'now': this_ts, 'alt_baro': altint, 'gscp': gs, 'lat': lat,
            'lon':long, 'track': track, 'hex': icao_num, 'flight': tail}

        if this_ts in allpoints:
            allpoints[this_ts].append(newdict)
        else:
            allpoints[this_ts] = [newdict]

        if first and altint > ALTTHRESH:
            airborne = True
            first = False
        else:
            first = False

        if this_datetime.time() >= scenicopen_datetime.time() and this_datetime.time() <= scenicclose_datetime.time():
            scenicskies = True
        else:
            scenicskies = False

        if this_datetime.time() < open_datetime.time() or this_datetime.time() > close_datetime.time():
            op_was_after_closing = True
        else:
            op_was_after_closing = False

        if airborne is True and altint < ALTTHRESH:
            #print("LANDED,%s,%s,%s,%s,%s" % (tail, op_was_after_closing, timestr(this_ts), datestr(this_ts), scenicskies))
            airborne = False
            prev_land_datetime = this_datetime

        if airborne is False and altint > ALTTHRESH and (this_datetime - prev_land_datetime > timedelta(minutes=TIMEGAPTHRESH)):
            #print("TAKEOFF,%s,%s,%s,%s,%s" % (tail, op_was_after_closing, timestr(this_ts), datestr(this_ts), scenicskies))
            airborne = True

        if tp_callback:
            tp_callback(icao_num, tail, lat, long, alt, timestr(this_ts))
    # print(json.dumps(output_json))
    return start_ts
