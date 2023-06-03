#!/usr/bin/python3
# Replay a directory of tar1090 trace archives, make available on a socket
# just like tar1090 running in realtime.
#
# Usage: parse_adsb.py <directory to scan> <port to accept connections on>

import os
import gzip
import json
from fnmatch import fnmatch
import signal
import socket
import time
from datetime import datetime
import sys

import readsb_parse

TIME_X = 30  # how many "x" versus real time to play back, or 0 for max
ANALYZE_LEN_SECS = 60*60*24*30
first_ts = 1662044400  #sep 1 7am: 1662040800 # 6:30 1662039000 # 8am 1662044400
#first_ts += 10*60

def locate_files(directory, pattern):
    allfiles = []
    for path, subdirs, files in os.walk(directory):
        for name in files:
            if fnmatch(name, pattern):
                allfiles.append(os.path.join(path, name))
    return allfiles

def parse_files(files):
    for file in files:
        fd = gzip.open(file, mode="r")
        jsondict = json.loads(fd.read())
        print(file + ": " + str(len(jsondict['trace'])) + " trace points")
        base_ts = readsb_parse.analyze(jsondict)
    return first_ts

class Socket:
    """Class representing a socket connection."""

    def __init__(self, ip, port):
        """Constructs a new Socket object with specified IP and port."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setblocking(False)
        self.socket.bind((ip, port))
        self.socket.listen(5)
        self.connections = []

    def accept(self):
        """Accepts incoming connections."""
        conn, addr = self.socket.accept()
        conn.setblocking(False)
        self.connections.append(conn)
        print(f"Connected to {addr} on {self.socket.getsockname()}")

    def sendall(self, data):
        """Sends data to all connected clients."""
        for conn in self.connections:
            try:
                conn.sendall(data)
            except socket.error as e:
                if e.errno == 32: # Broken pipe
                    conn.close()
                    self.connections.remove(conn)

    def close(self):
        """Close the socket connection."""
        self.socket.close()
        for conn in self.connections:
            conn.close()


def exit_handler(x, y):
    if sock1:
        sock1.close()
    if sock2:
        sock2.close()
    exit(1)


def main():
    global sock1, sock2
    sock1, sock2 = (None, None)
    signal.signal(signal.SIGINT, exit_handler)

    if len(sys.argv) < 3:
        print("Usage: parse_adsb.py <directory to scan> <port to accept connections on>")
        exit(1)

    files = locate_files(sys.argv[1], "*.json")
    parse_files(files)

    sock = Socket('127.0.0.1', int(sys.argv[2]))

    dummy_timestamp = {'flight': 'N/A'}

    # wait for first connection
    while True:
        try:
            sock.accept()
            break
        except socket.error:
            pass

    for k in list(range(first_ts, first_ts+ANALYZE_LEN_SECS)):
        try:
            sock.accept()
        except socket.error:
            pass

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
            sock.sendall(buffer)
            update_ctr += 1
            print(".", end="")

        done_work = time.time()
        work_time = done_work - start_work
        if TIME_X:
            sleeptime = (1/TIME_X) - work_time
            if sleeptime > 0.:
                time.sleep(sleeptime)

if __name__=="__main__":
    main()