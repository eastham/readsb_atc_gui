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

TIME_X = 30  # how many "x" versus real time to play back, 5000 max
ANALYZE_LEN_SECS = 60*60*6
start_date_string = '2022-09-01 13:30:00+00:00'  # UTC
#start_date_string = '2022-08-23 13:30:00+00:00'  # UTC

start_date_time = datetime.fromisoformat(start_date_string)
# start_date_time = datetime.strptime(start_date_string, '%Y-%m-%d %H:%M:%S')  
first_ts = int(start_date_time.timestamp()) 
print(f"Starting at {start_date_string} -- {first_ts}")

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
        # print(file + ": " + str(len(jsondict['trace'])) + " trace points")
        base_ts = readsb_parse.analyze(jsondict)
    return first_ts

class Socket:
    """Class representing a socket connection."""

    def __init__(self, ip, port):
        """Constructs a new Socket object with specified IP and port."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2097152)
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
    exit(1)

def main():
    DUMMY_TIMESTAMP = {'flight': 'N/A'}

    signal.signal(signal.SIGINT, exit_handler)

    if len(sys.argv) < 3:
        print("Usage: parse_adsb.py <directory to scan> <port to accept connections on>")
        exit(1)

    files = locate_files(sys.argv[1], "*.json")
    parse_files(files)
    print("Parse complete, ready to connect")

    sock = Socket('0.0.0.0', int(sys.argv[2]))

    # wait for first connection before starting data replay
    while True:
        try:
            sock.accept()
            break
        except socket.error:
            pass

    for k in list(range(first_ts, first_ts+ANALYZE_LEN_SECS)):
        try:
            sock.accept() # keep monitoring for new connections
        except socket.error:
            pass

        if datetime.utcfromtimestamp(k).second == 0:
            print("\n"+datetime.utcfromtimestamp(k).strftime('%Y-%m-%d %H:%M:%S'))

        start_work = time.time()
        update_ctr = 0

        if not k in readsb_parse.allpoints:
            # send dummy entry so the client can account for time passage w/ no a/c
            DUMMY_TIMESTAMP['now'] = k
            readsb_parse.allpoints[k] = [DUMMY_TIMESTAMP]

        for d in readsb_parse.allpoints[k]:
            string = json.dumps(d) + "\n"
            buffer = bytes(string, 'ascii')
            sock.sendall(buffer)
            update_ctr += 1
            print(".", end="", flush=True)

        done_work = time.time()
        work_time = done_work - start_work
        if TIME_X:
            sleeptime = (1./TIME_X) - work_time
            if sleeptime > 0.:
                time.sleep(sleeptime)

if __name__=="__main__":
    main()
