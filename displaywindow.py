import webview
import threading
import time

class DisplayWindow:
    def __init__(self, q, host):
        self.q = q
        self.window = None

        self.webview_thread = threading.Thread(target=self.focus_listener)
        self.webview_thread.start()
        self.window = webview.create_window('ADS-B display',
            "http://%s/tar1090/" % host)

        webview.start()

    def focus_listener(self):
        while True:
            id = self.q.get()
            self.focus(id)

    def focus(self, flight_id):
        call = "findPlanes(\"%s\", false, true, false, false, false)" % flight_id
        # print("eval_js call: "+call)
        self.window.evaluate_js(call)
