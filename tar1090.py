import os
import time
import webview
import argparse
from dbg import dbg, log
from multiprocessing import Process, Queue

TAR1090_HOST = '192.168.87.60'

def child(q, tarhost):
    print("Child starting pywebview")
    from displaywindow import DisplayWindow
    display_window = DisplayWindow(q, tarhost)

if __name__ == '__main__':
    # need to start a new process to allow both kivy and pywebview to have
    # their own main threads (each require it)
    q = Queue()
    p = Process(target=child, args=(q, TAR1090_HOST))
    p.start()

    print("Parent starting Kivy")
    import controller
    controller.run(q)
