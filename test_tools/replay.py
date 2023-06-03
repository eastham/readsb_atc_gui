#!/usr/bin/python3
# Replay a directory of tar1090 trace archives, make available on a socket
# just like tar1090 running in realtime.
#
# Usage: parse_adsb.py <directory to scan> <port to accept connections on>

import readsb_parse
import os
import gzip
import json
from fnmatch import fnmatch
import signal
import socket
import time
from datetime import datetime
import sys


class Socket:
    def __init__(self, ip, port):
        self.accept_socket = None
        self.ip = ip
        self.port = port

    def listen(self):
        self.accept_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.accept_socket.bind((self.ip, self.port))
        self.accept_socket.listen(5)
        conn, addr = self.accept_socket.accept()
        print(f"Connected on {self.port}")
        return conn
    
    def close(self):
        self.accept_socket.close()

def exit_handler(x,y):
    if sock1: sock1.close()
    if sock2: sock2.close()
    exit(1)

sock1, sock2 = (None, None)
signal.signal(signal.SIGINT, exit_handler)

TIME_X = 10  # how many "x" versus real time to play back, or 0 for max
# https://globe.adsbexchange.com/?replay=2022-09-01-15:00&lat=40.645&lon=-119.101&zoom=10.4
ANALYZE_LEN_SECS = 60*60*24*30
PATTERN = "*.json"
allfiles = []
first_ts = 1662044400  #sep 1 7am: 1662040800 # 6:30 1662039000 # 8am 1662044400
first_ts += 10*60

if len(sys.argv) < 3:
    print("Usage: parse_adsb.py <directory to scan> <port to accept connections on>")
    exit(1)

# locate all files to read
for path, subdirs, files in os.walk(sys.argv[1]):
    for name in files:
        if fnmatch(name, PATTERN):
            allfiles.append(os.path.join(path, name))

# read/parse files
for file in allfiles:
    fd = gzip.open(file, mode="r")
    jsondict = json.loads(fd.read())
    print(file + ": " + str(len(jsondict['trace'])) + " trace points")

    base_ts = readsb_parse.analyze(jsondict)
#    if not first_ts or first_ts > base_ts:
#        first_ts = base_ts

sock1 = Socket('127.0.0.1', int(sys.argv[2]))
conn1 = sock1.listen()
conn2 = None
if len(sys.argv) > 3:
    sock2 = Socket('127.0.0.1', int(sys.argv[3]))
    conn2 = sock2.listen()

dummy_timestamp = {'flight': 'N/A'}

for k in list(range(first_ts, first_ts+ANALYZE_LEN_SECS)):
    # print timestamp periodically to allow syncing with other data
    if datetime.utcfromtimestamp(k).second == 0:
        print(datetime.utcfromtimestamp(k).strftime('%Y-%m-%d %H:%M:%S'))

    start_work = time.time()
    update_ctr = 0

    if not k in readsb_parse.allpoints:
        # send dummy entry so the client can account for time passage w/ no a/c
        dummy_timestamp['now'] = k
        readsb_parse.allpoints[k] = [dummy_timestamp]

    for d in readsb_parse.allpoints[k]:
        string = json.dumps(d) + "\n"
        buffer = bytes(string, 'ascii')
        conn1.sendall(buffer)
        if (conn2): conn2.sendall(buffer)
        update_ctr += 1
        print(".", end="")

    done_work = time.time()
    work_time = done_work - start_work
    if TIME_X:
        sleeptime = (1/TIME_X) - work_time
        if sleeptime > 0.: time.sleep(sleeptime)


