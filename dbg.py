DEBUG = True

def dbg(*args, **kvargs):
    if DEBUG:
        print(*args, **kvargs)
