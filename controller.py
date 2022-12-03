import kivy
from kivy.config import Config
from kivy.clock import Clock, mainthread
import inspect
kivy.require('1.0.5')

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty


class Controller(FloatLayout):
    '''Create a controller that receives a custom widget from the kv lang file.

    Add an action to be called from the kv lang file.
    '''
    def add_strip_manual(self, id):
        print(id)

class FlightStrip(Button):
    def __init__(self, scrollview):
        self.scrollview = scrollview
        self.top_string = None
        super().__init__()

    def do_action(self):
        arrs = self.ids.arrivals_scroll
        self.newstrip = self.root.FlightStrip()
        arrs.add_widget(self.newstrip)

class AddButton(Button):
    def do_action(self, id):
        print("add ")

class ControllerApp(App):
    def __init__(self, read_thread):
        self.strips = {}    # dict of FlightStrips by id
        self.read_thread = read_thread
        super().__init__()


    def build(self):
        self.controller = Controller()

        return self.controller


    def add_button(self, scrollview):
        print(scrollview)
        #new_strip = FlightStrip()
        #scrollview.add_widget(new_strip, 1)
        #new_strip.text="foo"
        print(self.controller.ids["arrivals_scroll"].children[0])

        # test dynamic add of a new strip from the root controller
        new_strip = FlightStrip()
        #print(inspect.getmembers(sv, predicate=inspect.ismethod))
        self.controller.ids["arrivals_scroll"].children[0].add_widget(new_strip,0)
        new_strip.text="start"

        # test dynamic change of strip
        gv = self.controller.ids["arrivals_scroll"].children[0]
        gv.children[2].text="foo"

        # test remove
        gv.remove_widget(new_strip)

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

import aio
import threading
import time
listen = None
controllerapp = None

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

    Config.set('graphics', 'width', '600')
    Config.set('graphics', 'height', '800')

    # XXX should be separate thread
#    event = Clock.schedule_interval(read_adsb_callback, 1 / 100.)
#    event = Clock.schedule_interval(expire_old_flights_cb, 1)
    event = Clock.schedule_once(start_reader, 5)
    event = Clock.schedule_once(aio.sixs_test, 15)
    read_thread = threading.Thread(target=procline_loop)
    controllerapp = ControllerApp(read_thread)
    controllerapp.run()
