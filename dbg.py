import datetime

debug_level = False
TEST = True

def set_dbg_level(l):
    global debug_level
    debug_level = l

def log(*args, **kvargs):
    if debug_level > 0:
        do_log(args, kvargs)

def dbg(*args, **kvargs):
    if debug_level > 1:
        do_log(args, kvargs)

def do_log(args, kvargs):
    dt = datetime.datetime.today()
    print(dt.strftime("%H:%M:%S: "), end='')
    print(*args, **kvargs)

def run_test(f):
    if TEST:
        f()
