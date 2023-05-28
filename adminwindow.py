import webview
import threading
import time
import signal
import argparse
from dbg import dbg, set_dbg_level, get_dbg_level, log

from appsheet_api import Appsheet
from config import Config

class AdminWindow:
    def __init__(self, q):
        self.q = q
        self.window = None
        self.appsheet = Appsheet()

        self.webview_thread = threading.Thread(target=self.focus_listener)
        self.webview_thread.start()
        self.config = Config()
        self.window = webview.create_window('Admin Display',
            self.config.private_vars['appsheet']['start_url'])

        signal.signal(signal.SIGINT, lambda x,y: exit(1))

        set_dbg_level(2)

        webview.start(debug=True)

    def focus_listener(self):
        while True:
            id = self.q.get()
            self.focus(id)

    def focus(self, tail):
        if not tail: return
        call = ("window.location.href = '" +
            self.config.private_vars['appsheet']['goto_aircraft_url'] +
            tail + "'")
        self.window.evaluate_js(call)
