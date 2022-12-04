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
    def __init__(self, index, app, id):
        self.scrollview_index = index
        self.top_string = None
        self.note_string = ""
        self.alt_string = ""
        self.id = id
        self.app = app
        super().__init__()

    def do_click(self):
        controllerapp.dialog.show_custom_dialog(self.app, self.id)

    def update_strip_text(self):
        self.text = self.top_string + "\n" + self.alt_string + "\n" + self.note_string

    def get_scrollview(self):
        scrollbox_name = "scroll_%d" % self.scrollview_index
        return self.app.controller.ids[scrollbox_name].children[0]

    def unrender(self):
        self.get_scrollview().remove_widget(self)

    def render(self):
        self.get_scrollview().add_widget(self, index=100)

class ControllerApp(MDApp):
    def __init__(self, read_thread):
        dbg("controller init")
        self.strips = {}    # dict of FlightStrips by id
        self.read_thread = read_thread
        self.dialog = None
        self.OMIT_INDEX = 3  # don't move to this index

        super().__init__()

    def build(self):
        dbg("controller build")
        self.controller = Controller()
        self.dialog = Dialog()
        self.theme_cls.theme_style="Dark"
        dbg("controller build done")
        return self.controller

    @mainthread
    def update_strip(self, id, bbox_index: int):  # XXX misnamed
        move = False

        if id in self.strips:
            strip = self.strips[id]

            if bbox_index < 0:
                bbox_index = strip.scrollview_index # don't move but continue to update

            if strip.scrollview_index != bbox_index and bbox_index != self.OMIT_INDEX:
                strip.unrender()
                dbg("bbox update")
                strip.scrollview_index = bbox_index
                move = True
            else:
                return
        else:
            if bbox_index < 0:
                return
            dbg("new flightstrip %s" % id)
            strip = FlightStrip(bbox_index, self, id)
            self.strips[id] = strip

        if not move:
            self.set_strip_color(id, (1,1,1))
            Clock.schedule_once(lambda dt: self.set_strip_color(id, (.5,.5,.5)), 5)

        strip.render()
        strip.text = strip.top_string =  id
        strip.update_strip_text()

    @mainthread
    def remove_strip(self, id, index):
        try:
            strip = self.strips[id]
        except:
            return
        print("removing flight %s" % id)
        strip.unrender()
        del self.strips[id]

    @mainthread
    def update_strip_alt(self, id, altstr, alt, gs):
        try:
            strip = self.strips[id]
        except:
            return
        strip.alt_string = altstr + " " + str(alt) + " " + str(int(gs))
        strip.update_strip_text()

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



def sock_read_loop():
    last_expire = time.time()

    while True:
        aio.sock_read(listen, controllerapp)
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

    Clock.schedule_once(start_reader, 2)
    dbg("Scheduling complete")

    read_thread = threading.Thread(target=sock_read_loop)
    controllerapp = ControllerApp(read_thread)

    dbg("Starting main loop")
    controllerapp.run()
