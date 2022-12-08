import datetime

debug_level = False
TEST = True

def set_dbg_level(l):
    global debug_level
    debug_level = l

def dbg(*args, **kvargs):
    if debug_level:
        dt = datetime.datetime.today()
        print(dt.strftime("%H:%M:%S: "), end='')
        print(*args, **kvargs)

def test(f):
    if TEST:
        f()
