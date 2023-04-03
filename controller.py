import kivy
kivy.require('1.0.5')
from kivy.config import Config
Config.set('graphics', 'width', '600')
Config.set('graphics', 'height', '800')
from kivy.clock import Clock, mainthread
from kivymd.app import MDApp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty

import signal
import threading
import time
import webbrowser
import argparse

import adsb_receiver
from dialog import Dialog
from dbg import dbg, set_dbg_level, log
from test import tests_enable
from bboxes import Bboxes
from flight import Flight
from displaywindow import DisplayWindow

controllerapp = None

class Controller(FloatLayout):
    def do_add_click(self, n):
        dbg("add click %d" % n)

class FlightStrip:
    def __init__(self, index, app, id, focus_q, admin_q):
        self.scrollview_index = index
        self.app = app
        self.id = id
        self.focus_q = focus_q
        self.admin_q = admin_q

        self.top_string = None
        self.note_string = ""
        self.alt_string = ""
        self.loc_string = ""
        self.deanno_event = None

        self.layout = GridLayout(cols=2, row_default_height=150, height=150, size_hint_y=None)
        self.main_button = Button(size_hint_x=None, padding=(10,10),
            text_size=(500,110), width=500, height=225, halign="left",
            valign="top", markup=True, on_release=self.main_button_click)

        self.right_layout = GridLayout(rows=3, row_default_height=50)

        self.admin_button = Button(text='Admin', size_hint_x=None, width=100,
            on_release=self.admin_click)
        self.focus_button = Button(text='Focus', size_hint_x=None, width=100,
            on_release=self.focus_click)
        self.web_button = Button(text='Web', size_hint_x=None, width=100,
            on_release=self.web_click)

        self.layout.add_widget(self.main_button)
        self.layout.add_widget(self.right_layout)
        self.right_layout.add_widget(self.admin_button)
        self.right_layout.add_widget(self.focus_button)
        self.right_layout.add_widget(self.web_button)

    def main_button_click(self, arg):
        controllerapp.dialog.show_custom_dialog(self.app, self.id)

    def admin_click(self, arg):
        dbg("admin " + self.id)
        if self.admin_q: self.admin_q.put(self.id)

    def web_click(self, arg):
        webbrowser.open("https://flightaware.com/live/flight/" + self.id)

    def focus_click(self, arg):
        dbg("focus " + self.id)
        if self.focus_q: self.focus_q.put(self.id)

    def update_strip_text(self):
        self.main_button.text = (self.top_string + " " + self.loc_string +
            "\n" + self.alt_string + " " + self.note_string)

    def get_scrollview(self):
        scrollbox_name = "scroll_%d" % self.scrollview_index
        return self.app.controller.ids[scrollbox_name].children[0]

    def update(self, flight, location, bboxes_list):
        self.top_string = "[b][size=34]%s[/size][/b]" % flight.flight_id

        bbox_2nd_level = flight.get_bbox_at_level(1, bboxes_list)
        self.loc_string = bbox_2nd_level.name if bbox_2nd_level else ""

        altchangestr = flight.get_alt_change_str(location.alt_baro)
        self.alt_string = altchangestr + " " + str(location.alt_baro) + " " + str(int(location.gs))

        self.update_strip_text()

    def set_highlight(self):
        self.main_button.background_color = (1,.7,.7)
        Clock.schedule_once(lambda dt: self.set_normal(), 5)

    def set_normal(self):
        self.main_button.background_color = (.8,.4,.4)

    def unrender(self):
        self.get_scrollview().remove_widget(self.layout)

    def render(self):
        self.get_scrollview().add_widget(self.layout, index=100)

    def annotate(self, note):
        print("**** annotate " + note)

        self.note_string = note
        if self.deanno_event:
            Clock.unschedule(self.deanno_event)
        self.deanno_event = Clock.schedule_once(lambda dt: self.deannotate(), 5)
        self.main_button.background_color = (1,1,0)

        self.update_strip_text()

    def deannotate(self):
        self.note_string = ""
        self.set_normal()
        self.update_strip_text()



class ControllerApp(MDApp):
    def __init__(self, bboxes, focus_q, admin_q):
        dbg("controller init")
        self.strips = {}    # dict of FlightStrips by id
        self.dialog = None
        self.OMIT_INDEX = 3  # don't move strips TO this scrollview index.  XXX move to KML?
        self.MAX_SCROLLVIEWS = 4
        self.bboxes = bboxes
        self.focus_q = focus_q
        self.admin_q = admin_q

        super().__init__()

    def build(self):
        dbg("controller build")
        self.controller = Controller()
        self.dialog = Dialog()
        self.theme_cls.theme_style="Dark"
        self.setup_titles()
        dbg("controller build done")
        return self.controller

    def get_title_button_by_index(self, index):
        title_id = "title_%d" % index
        return self.controller.ids[title_id]

    def setup_titles(self):
        """Set GUI title bars according to bbox/KML titles"""
        for i, bbox in enumerate(self.bboxes.boxes):
            title_button = self.get_title_button_by_index(i)
            title_button.text = bbox.name
            if i >= self.MAX_SCROLLVIEWS-1: return

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
            strip = FlightStrip(new_scrollview_index, self, id, self.focus_q, self.admin_q)
            strip.update(flight, flight.lastloc, flight.bboxes_list)
            strip.render()
            strip.set_highlight()

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
        strip.annotate(note)
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

def run(focus_q, admin_q):
    parser = argparse.ArgumentParser(description="match flights against kml bounding boxes")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument('--test', help="add some test flights", action="store_true")
    parser.add_argument('file', nargs='+', help="kml files to use")
    parser.add_argument('--ipaddr', help="IP address to connect to", required=True)
    parser.add_argument('--port', help="port to connect to", required=True)

    args = parser.parse_args()
    if args.debug: set_dbg_level(2)
    elif args.verbose: set_dbg_level(1)
    if args.test: tests_enable()

    bboxes_list = []
    for f in args.file:
        bboxes_list.append(Bboxes(f))

    signal.signal(signal.SIGINT, sigint_handler)
    listen_socket = adsb_receiver.setup(args.ipaddr, args.port)

    global controllerapp
    controllerapp = ControllerApp(bboxes_list[0], focus_q, admin_q)
    read_thread = threading.Thread(target=adsb_receiver.flight_read_loop,
        args=[listen_socket, bboxes_list, controllerapp.update_strip,
        controllerapp.remove_strip, controllerapp.annotate_strip, None])
    Clock.schedule_once(lambda x: read_thread.start(), 2)

    dbg("Starting main loop")
    controllerapp.run()

if __name__ == '__main__':
    run(None, None)
