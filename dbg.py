debug_level = True
TEST = True

def set_dbg_level(l):
    debug_level = l

def dbg(*args, **kvargs):
    if debug_level:
        print(*args, **kvargs)

def test(f):
    if TEST:
        f()
