DEBUG = True
TEST = True

def dbg(*args, **kvargs):
    if DEBUG:
        print(*args, **kvargs)

def test(f):
    if TEST:
        f()
