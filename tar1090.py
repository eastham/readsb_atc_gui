import os
import time
import webview
import argparse
from multiprocessing import Process, Queue

from dbg import dbg, log
from config import Config

def display_child(q):
    print("Child starting pywebview")
    from displaywindow import DisplayWindow
    display_window = DisplayWindow(q)

def admin_child(q):
    print("Child starting admin")
    from adminwindow import AdminWindow
    admin_window = AdminWindow(q)

if __name__ == '__main__':
    config = Config()

    # need to start a new process to allow both kivy and pywebview to have
    # their own main threads (each require it)
    display_q = Queue()
    p = Process(target=display_child, args=(display_q,))
    p.start()

    admin_q = None
    if config.vars['admin']['enable']:
        admin_q = Queue()
        p = Process(target=admin_child, args=(admin_q,))
        p.start()

    print("Parent starting Kivy")
    import controller
    controller.run(display_q, admin_q)
