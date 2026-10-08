import time


# Changes every time the server (re)starts, e.g. after "Reload" on
# PythonAnywhere, so browsers download the new CSS/JS instead of
# reusing an old cached copy.
STATIC_VERSION = str(int(time.time()))


def static_version(request):
    """
    Adds {{ ts }} to every template, used as ?v={{ ts }} on static links.
    """

    return {"ts": STATIC_VERSION}
