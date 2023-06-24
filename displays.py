from multiprocessing import Process, Queue
from config import Config
from displaywindow import DisplayWindow
from adminwindow import AdminWindow

def display_child(q):
    '''starts the flight strip display'''
    print("Child starting pywebview")

    DisplayWindow(q)

def admin_child(q):
    '''starts the window for the administrative gui'''
    print("Child starting admin")
    AdminWindow(q)

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
