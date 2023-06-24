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

process = None
def run(cmd):
    global process
    process = subprocess.Popen(cmd)
    process.communicate()

def handle_sigint(sig, frame):
    print("CTRL-C detected, killing subprocess...")
    global process
    if process is not None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    sys.exit(1)

signal.signal(signal.SIGINT, handle_sigint)

def send_slack(app, msg):
    text = f"{app} DIED, will retry in {RESTART_DELAY} seconds -- WITH MESSAGE {msg}"
    webhook = CONFIG.private_vars['slack_webhook']
    payload = {"text": text}
    response = requests.post(webhook, json.dumps(payload))
    print(response)

if __name__ == "__main__":
    while True:
        run(sys.argv[1:])
        try:
            send_slack(str(sys.argv[1:2]), "")
        except Exception as e:
            print(f"Slack logging failed: {str(e)}")
        time.sleep(RESTART_DELAY)
