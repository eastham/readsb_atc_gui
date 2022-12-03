import kivy
from kivy.config import Config
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
listen = None
controllerapp = None

class Controller(FloatLayout):
    def __init__(self):
        pass

class FlightStrip(Button):
    def __init__(self, scrollview):
        self.scrollview = scrollview
        self.top_string = None
        super().__init__()

    def do_click(self):
        controllerapp.dialog.show_custom_dialog()

class ControllerApp(MDApp):
    def __init__(self, read_thread):
        self.strips = {}    # dict of FlightStrips by id
        self.read_thread = read_thread
        self.dialog = None
        super().__init__()

    def build(self):
        self.controller = Controller()
        self.dialog = Dialog()
        self.theme_cls.theme_style="Dark"
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
        new_strip = FlightStrip(scrollview)

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
        strip.text = strip.top_string + "\n" + altstr + " " + str(alt)

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

    Config.set('graphics', 'width', '500')
    Config.set('graphics', 'height', '800')

    # XXX should be separate thread
#    event = Clock.schedule_interval(read_adsb_callback, 1 / 100.)
#    event = Clock.schedule_interval(expire_old_flights_cb, 1)
    event = Clock.schedule_once(start_reader, 3)
    event = Clock.schedule_once(aio.sixs_test, 15)
    read_thread = threading.Thread(target=procline_loop)
    controllerapp = ControllerApp(read_thread)
    controllerapp.run()
