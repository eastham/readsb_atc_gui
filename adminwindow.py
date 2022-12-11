import webview
import threading
import time
import signal

from appsheet import Appsheet
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

        webview.start(debug=True)

    def focus_listener(self):
        while True:
            id = self.q.get()
            self.focus(id)

    def focus(self, flight_id):
        key = self.appsheet.id_to_key(flight_id)
        if key and len(key):
            call = ("window.location.href = '" +
                self.config.private_vars['appsheet']['focus_url'] +
                key + "'")
            self.window.evaluate_js(call)
