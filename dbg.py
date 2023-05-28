import datetime
import pprint

debug_level = False
pp = pprint.PrettyPrinter(indent=4)

def set_dbg_level(l):
    global debug_level
    debug_level = l

def get_dbg_level():
    return debug_level

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

def ppdbg(arg):
    if debug_level > 1:
        pp.pprint(arg)

def ppd(arg):
    pp.pprint(arg)
