import webview
import threading
import time
import signal

from config import Config

class DisplayWindow:
    def __init__(self, q):
        self.q = q
        self.window = None

        config = Config()
        self.webview_thread = threading.Thread(target=self.focus_listener)
        self.webview_thread.start()
        conf = config.vars["tar1090"]
        self.window = webview.create_window('ADS-B display',
            "http://%s/tar1090/%s" % (conf["host"], conf["args"]))
        signal.signal(signal.SIGINT, lambda x,y: exit(1))

        webview.start(debug=False)

    def focus_listener(self):
        while True:
            id = self.q.get()
            self.focus(id)

    def focus(self, flight_id):
        call = "findPlanes(\"%s\", false, true, false, false, false)" % flight_id
        # print("eval_js call: "+call)
        self.window.evaluate_js(call)
