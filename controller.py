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

import signal
import threading
import time
import webbrowser
import argparse

import adsb_receiver
from dialog import Dialog
from dbg import dbg, set_dbg_level
from bboxes import Bboxes

controllerapp = None
SERVER_REFRESH_RATE = 60 # seconds

USE_APPSHEET = True
if USE_APPSHEET:
    import appsheet_api
    appsheet = appsheet_api.Appsheet()
else:
    appsheet = None

class Controller(FloatLayout):
    def do_add_click(self, n):
        dbg("add click %d" % n)

class FlightStrip:
    def __init__(self, index, app, flight, id, tail, focus_q, admin_q):
        self.scrollview_index = index
        self.app = app
        self.flight = flight
        self.id = id # redundant to flight?
        self.tail = tail# redundant to flight?
        self.focus_q = focus_q
        self.admin_q = admin_q
        self.bg_color_warn = False
        self.update_thread = None
        self.stop_event = threading.Event()

        self.top_string = None
        self.note_string = ""
        self.alt_string = ""
        self.loc_string = ""
        self.deanno_event = None

        self.layout = GridLayout(cols=2, row_default_height=150, height=150, size_hint_y=None)
        self.main_button = Button(size_hint_x=None, padding=(10,10),
            text_size=(500,150), width=500, height=225, halign="left",
            valign="top", markup=True, on_release=self.main_button_click)

        self.right_layout = GridLayout(rows=3, row_default_height=50)

        self.admin_button = Button(text='Open', size_hint_x=None, width=100,
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

        self.update_thread = threading.Thread(target=self.server_refresh_thread, args=[flight])
        self.update_thread.start()

    def __del__(self):
        dbg(f"Deleting strip {self.id}")

    def main_button_click(self, arg):
        #controllerapp.dialog.show_custom_dialog(self.app, self.id)
        pass

    def admin_click(self, arg):
        if 'Row ID' not in self.flight.flags:
            self.do_server_update(self.flight) # hopefully sets row id

        if 'Row ID' in self.flight.flags:
            if self.admin_q: self.admin_q.put(self.flight.flags['Row ID'])
        return

    def web_click(self, arg):
        webbrowser.open("https://flightaware.com/live/flight/" + self.id)

    def focus_click(self, arg):
        dbg("focus " + self.id)
        if self.focus_q: self.focus_q.put(self.id)

    def update_strip_text(self):
        self.main_button.text = (self.top_string + " " + self.loc_string +
            "\n" + self.alt_string + "\n" + self.note_string)

    def get_scrollview(self):
        scrollbox_name = "scroll_%d" % self.scrollview_index
        return self.app.controller.ids[scrollbox_name].children[0]

    def stop_server_loop(self):
        dbg("stop_server_loop, thread " + str(self.update_thread))
        self.stop_event.set()

    def do_server_update(self, flight):
        tail = flight.tail if flight.tail else flight.flight_id.strip()

        dbg("do_server_update: " + tail)
        try:
            # TODO could optimize: only if unregistered?
            obj = appsheet.aircraft_lookup(tail, wholeobj=True)
            self.note_string = ""

            if obj:
                flight.flags['Row ID'] = obj['Row ID']
                self.note_string += "Arrivals=%s " % obj['Arrivals']

            if not obj:
                self.note_string += "**unreg** "
                self.bg_color_warn = True
            else:
                if not test_dict(obj, 'Registered online'):
                    if not test_dict(obj, 'IsBxA'):
                        self.note_string += "**manual reg** "
                        self.bg_color_warn = True

            if test_dict(obj, 'IsBxA'):
                self.note_string += "BxA"
                self.bg_color_warn = False

        except Exception:
            dbg("do_server_update parse failed")
            pass

        self.set_normal()
        self.update(flight, None, None)
        dbg("done running update_from_server " + tail)

    def server_refresh_thread(self, flight):
        """This thread periodically refreshes aircraft details with the server."""
        if not appsheet: return
        while not self.stop_event.is_set():
            self.do_server_update(flight)
            time.sleep(SERVER_REFRESH_RATE)
        dbg("Exited refresh thread")

    def update(self, flight, location, bboxes_list):
        """ Re-build strip strings, changes show up on-screen automatically """
        # dbg(f"strip.update for {flight.tail}")
        if (flight.flight_id.strip() != flight.tail and flight.tail):
            extratail = flight.tail
        else:
            extratail = ""
        self.top_string = "[b][size=34]%s %s[/size][/b]" % (flight.flight_id.strip(),
            extratail)

        if location and bboxes_list:
            bbox_2nd_level = flight.get_bbox_at_level(1, bboxes_list)

            # XXX hack to keep string from wrapping...not sure how to get kivy
            # to do this
            cliplen = 23 - len(flight.flight_id.strip()) - len(extratail)
            if cliplen < 0: cliplen = 0
            self.loc_string = bbox_2nd_level.name[0:cliplen] if bbox_2nd_level else ""

            altchangestr = flight.get_alt_change_str(location.alt_baro)
            self.alt_string = altchangestr + " " + str(location.alt_baro) + " " + str(int(location.gs))

        self.update_strip_text()

    def set_highlight(self):
        self.main_button.background_color = (1,.7,.7)
        Clock.schedule_once(lambda dt: self.set_normal(), 5)

    def set_normal(self):
        if self.bg_color_warn:
            self.main_button.background_color = (.8,.2,.2)
        else:
            self.main_button.background_color = (.4,.8,.4)

    def unrender(self):
        self.get_scrollview().remove_widget(self.layout)

    def render(self):
        self.get_scrollview().add_widget(self.layout, index=100)

    def annotate(self, note):
        dbg("**** annotate " + note)

        self.note_string = note
        if self.deanno_event:
            Clock.unschedule(self.deanno_event)
        self.deanno_event = Clock.schedule_once(lambda dt: self.deannotate(), 10)
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
        """ Called on bbox change. """
        new_scrollview_index = flight.inside_bboxes[0]
        id = flight.flight_id

        if id in self.strips:
            strip = self.strips[id]
            strip.update(flight, flight.lastloc, flight.bboxes_list)
            if new_scrollview_index < 0 and strip.scrollview_index >= 0:  # no longer in a tracked region
                # don't move strip but continue to update indefinitely
                # XXX probably not right behavior for everyone
                return
            if strip.scrollview_index != new_scrollview_index:
                # move strip to new scrollview

                strip.unrender()
                strip.scrollview_index = new_scrollview_index
                strip.render()
        else:
            if new_scrollview_index < 0:
                return # not in a tracked region now, don't add it
            # location is inside one of our tracked regions, add new strip

            strip = FlightStrip(new_scrollview_index, self, flight, id, flight.tail,
                self.focus_q, self.admin_q)
            strip.update(flight, flight.lastloc, flight.bboxes_list)
            strip.render()
            strip.set_highlight()

            self.strips[id] = strip

    @mainthread
    def remove_strip(self, flight):
        try:
            strip = self.strips[flight.flight_id]
        except KeyError:
            return
        dbg("removing flight %s" % flight.flight_id)
        strip.unrender()
        strip.stop_server_loop()
        del self.strips[flight.flight_id]

    @mainthread
    def annotate_strip(self, flight1, flight2, lat_dist, alt_dist):
        dbg("annotate strip "+flight1.flight_id)
        id1 = flight1.flight_id
        id2 = flight2.flight_id
        try:
            strip = self.strips[id1]
        except KeyError:
            dbg("annotate not found")
            return
        note = "TRAFFIC ALERT: "+id2
        strip.annotate(note)
        strip.update_strip_text()

    @mainthread
    def set_strip_color(self, id, color):
        try:
            strip = self.strips[id]
        except KeyError:
            return
        strip.background_color = color

def sigint_handler(signum, frame):
    exit(1)

def test_dict(d, key):
    if not d: return False
    if not key in d: return False
    if d[key] == '' or d[key] == 'N': return False
    return True

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
