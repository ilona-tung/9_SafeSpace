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


def pending_counts(request):
    """
    {{ pending_count }}: friend requests and Together invites waiting
    for the logged-in user, shown next to "Profile" in the menu.
    """

    user = getattr(request, "user", None)

    if user is None or not user.is_authenticated or user.is_staff:
        return {}

    return {
        "pending_count": (
            user.friendship_requests_received.filter(status="pending").count()
            + user.together_invites_received.filter(status="pending").count()
        )
    }
