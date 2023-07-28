#!/usr/bin/python3
"""Run command given in argv repeatedly in case of crashes"""

import json
import os
import signal
import subprocess
import sys
import time
import requests
from config import Config

RESTART_DELAY = 60 # seconds
CONFIG = Config()
SEND_SLACK = False

process = None
def run(cmd):
    global process
    pid = os.getpid()
    cwd = os.getcwd()
    fn = os.path.basename(cmd[0])

    pidfn = os.path.join(cwd, f"{fn}-{pid}-pid.txt")
    outfn = os.path.join(cwd, f"{fn}-{pid}-stdout.txt")
    errfn = os.path.join(cwd, f"{fn}-{pid}-stderr.txt")
    print(pidfn)

    with open(outfn, "wb", flush=True) as out, open(errfn, "wb", flush=True) as err:
        process = subprocess.Popen(cmd, stdout=out, stderr=err)

        pid = process.pid
        with open(pidfn, 'wt', encoding='utf-8') as pid_file:
            pid_file.write(str(pid) + '\n')

        process.communicate()

    endstr = (f"***End of stdout was:\n {read_last_lines(outfn)}\n"
             f"***End of stderr was:\n {read_last_lines(errfn)}")
    return endstr

def read_last_lines(filename, num_lines=20):
    with open(filename, 'r') as file:
        lines = file.readlines()
    return lines[-num_lines:]

def handle_sigint(sig, frame):
    print("CTRL-C detected, killing subprocess...")
    global process
    if process is not None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    sys.exit(1)

signal.signal(signal.SIGINT, handle_sigint)

def send_slack(app, msg):
    text = f"{app} DIED, will retry in {RESTART_DELAY} seconds -- {msg}"
    print(text)
    if SEND_SLACK:
        webhook = CONFIG.private_vars['slack_webhook']
        payload = {"text": text}
        response = requests.post(webhook, json.dumps(payload))
        print(response)
    else:
        print("Skipping slack send")

if __name__ == "__main__":
    while True:
        result = run(sys.argv[1:])
        try:
            send_slack(str(sys.argv[1:2]), result)
        except Exception as e:
            print(f"Slack logging failed: {str(e)}")
        time.sleep(RESTART_DELAY)
