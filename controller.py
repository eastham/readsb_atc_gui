import kivy
kivy.require('1.0.5')
from kivy.config import Config
Config.set('graphics', 'width', '600')
Config.set('graphics', 'height', '800')
from kivy.clock import Clock, mainthread
from kivymd.app import MDApp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty

import signal
import threading
import time

import adsb_receiver
from dialog import Dialog
from dbg import dbg, test, set_dbg_level
from bboxes import Bboxes
from flight import Flight

listen = None
controllerapp = None

class Controller(FloatLayout):
    def do_add_click(self, n):
        dbg("add click %d" % n)

class FlightStrip(Button):
    def __init__(self, index, app, id):
        self.scrollview_index = index
        self.top_string = None
        self.note_string = ""
        self.alt_string = ""
        self.loc_string = ""
        self.id = id
        self.app = app
        super().__init__()

    def do_click(self):
        controllerapp.dialog.show_custom_dialog(self.app, self.id)

    def update_strip_text(self):
        self.text = self.top_string + " " + self.loc_string + "\n" + self.alt_string + "\n" + self.note_string

    def get_scrollview(self):
        scrollbox_name = "scroll_%d" % self.scrollview_index
        return self.app.controller.ids[scrollbox_name].children[0]

    def update(self, flight, location, bboxes_list):
        self.top_string = flight.flight_id

        bbox_2nd_level = flight.get_bbox_at_level(1, bboxes_list)
        self.loc_string = bbox_2nd_level.name if bbox_2nd_level else ""

        altchangestr = flight.get_alt_change_str(location.alt_baro)
        self.alt_string = altchangestr + " " + str(location.alt_baro) + " " + str(int(location.gs))

        self.update_strip_text()

    def unrender(self):
        self.get_scrollview().remove_widget(self)

    def render(self):
        self.get_scrollview().add_widget(self, index=100)

class ControllerApp(MDApp):
    def __init__(self):
        dbg("controller init")
        self.strips = {}    # dict of FlightStrips by id
        self.dialog = None
        self.OMIT_INDEX = 3  # don't move strips to this index

        super().__init__()

    def build(self):
        dbg("controller build")
        self.controller = Controller()
        self.dialog = Dialog()
        self.theme_cls.theme_style="Dark"
        dbg("controller build done")
        return self.controller

    @mainthread
    def update_strip(self, flight):
        move = False
        new_scrollview_index = flight.inside_bboxes[0]
        id = flight.flight_id

        if id in self.strips:
            strip = self.strips[id]
            strip.update(flight, flight.lastloc, flight.bboxes_list)

            if new_scrollview_index < 0:  # no longer in a tracked region
                # don't move strip but continue to update indefinitely
                return
            if strip.scrollview_index != new_scrollview_index and new_scrollview_index != self.OMIT_INDEX:
                # move strip to new scrollview
                strip.unrender()
                strip.scrollview_index = new_scrollview_index
                move = True
                strip.render()
        else:
            if new_scrollview_index < 0:
                return # not in a tracked region now, don't add it
            # location is inside one of our tracked regions, add new strip
            dbg("new flightstrip %s" % id)
            strip = FlightStrip(new_scrollview_index, self, id)
            strip.update(flight, flight.lastloc, flight.bboxes_list)
            strip.render()
            self.set_strip_color(id, (1,.7,.7))  # highlight new strip
            Clock.schedule_once(lambda dt: self.set_strip_color(id, (.8,.4,.4)), 5)

            self.strips[id] = strip


    @mainthread
    def remove_strip(self, flight):
        try:
            strip = self.strips[flight.flight_id]
        except:
            return
        dbg("removing flight %s" % flight.flight_id)
        strip.unrender()
        del self.strips[flight.flight_id]

    @mainthread
    def annotate_strip(self, id, note):
        try:
            strip = self.strips[id]
        except:
            return
        strip.note_string = note
        strip.update_strip_text()

    @mainthread
    def set_strip_color(self, id, color):
        try:
            strip = self.strips[id]
        except:
            return
        strip.background_color = color

def sigint_handler(signum, frame):
    exit(1)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="match flights against kml bounding boxes")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument('file', nargs='+', help="kml files to use")
    parser.add_argument('--ipaddr', help="IP address to connect to", required=True)
    parser.add_argument('--port', help="port to connect to", required=True)
    args = parser.parse_args()

    bboxes_list = []
    if args.verbose: set_dbg_level(True)
    for f in args.file:
        bboxes_list.append(Bboxes(f))

    signal.signal(signal.SIGINT, sigint_handler)
    listen_socket = adsb_receiver.setup(args.ipaddr, args.port)

    controllerapp = ControllerApp()
    read_thread = threading.Thread(target=adsb_receiver.flight_read_loop,
        args=[listen_socket, bboxes_list, controllerapp.update_strip, controllerapp.remove_strip])
    Clock.schedule_once(lambda x: read_thread.start(), 2)

    dbg("Starting main loop")
    controllerapp.run()
