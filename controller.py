import kivy
from kivy.config import Config
Config.set('graphics', 'width', '600')
Config.set('graphics', 'height', '800')

from kivy.clock import Clock, mainthread
from kivymd.app import MDApp
import inspect
kivy.require('1.0.5')

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty

import aio
import threading
import time
from dialog import Dialog
from dbg import dbg, test

listen = None
controllerapp = None

class Controller(FloatLayout):
    def __init__(self):
        super().__init__()
        pass

class FlightStrip(Button):
    def __init__(self, scrollview, app, id):
        self.scrollview = scrollview
        self.top_string = None
        self.note_string = ""
        self.alt_string = ""
        self.id = id
        self.app = app
        super().__init__()

    def do_click(self):
        controllerapp.dialog.show_custom_dialog(self.app, self.id)

class ControllerApp(MDApp):
    def __init__(self, read_thread):
        dbg("controller init")
        self.strips = {}    # dict of FlightStrips by id
        self.read_thread = read_thread
        self.dialog = None
        super().__init__()

    def build(self):
        dbg("controller build")
        self.controller = Controller()
        self.dialog = Dialog()
        self.theme_cls.theme_style="Dark"
        dbg("controller build done")
        return self.controller

    @mainthread
    def add_flight(self, id, bbox):
        if id in self.strips:
            print("warning: flight already on gui %s" % id)
            return
        #print(inspect.getmembers(sv, predicate=inspect.ismethod))
        print("**** add_flight %s %s" % (id, str(bbox)))

        scrollbox_name = "scroll_%d" % bbox.index
        scrollview = self.controller.ids[scrollbox_name].children[0]
        new_strip = FlightStrip(scrollview, self, id)

        self.controller.ids[scrollbox_name].children[0].add_widget(new_strip, index=100)
        new_strip.text = new_strip.top_string =  "%s %s" % (id, bbox.name)

        self.strips[id] = new_strip


    @mainthread
    def remove_flight(self, id, index):
        strip = self.strips[id]
        print("removing flight %s" % id)
        scrollview = strip.scrollview
        scrollview.remove_widget(strip)
        del self.strips[id]

    @mainthread
    def update_flight(self, id, altstr, alt):
        strip = self.strips[id]
        strip.alt_string = altstr + " " + str(alt)
        self.update_strip_text(strip)

    @mainthread
    def annotate_flight(self, id, note):
        strip = self.strips[id]
        strip.note_string = note
        self.update_strip_text(strip)

    def update_strip_text(self, strip):
        strip.text = strip.top_string + "\n" + strip.alt_string + "\n" + strip.note_string

    @mainthread
    def set_flight_color(self, id, color):
        try:
            strip = self.strips[id]
        except:
            return
        strip.background_color = color



def read_adsb_callback(dt):
    aio.procline(listen, controllerapp)

def procline_loop():
    last_expire = time.time()

    while True:
        aio.procline(listen, controllerapp)
        if time.time() - last_expire > 1:
            aio.expire_old_flights(controllerapp)
            last_expire = time.time()

import signal

def handler(signum, frame):
    exit(1)

read_thread = None

def start_reader(dt):
    read_thread.start()  # XXX race cond, call start from init


if __name__ == '__main__':
    signal.signal(signal.SIGINT, handler)

    listen = aio.setup()

    test(lambda: Clock.schedule_once(start_reader, 2))
    test(lambda: Clock.schedule_once(aio.sixs_test, 15))
    dbg("Scheduling complete")

    read_thread = threading.Thread(target=procline_loop)
    controllerapp = ControllerApp(read_thread)


    dbg("Starting main loop")
    controllerapp.run()
