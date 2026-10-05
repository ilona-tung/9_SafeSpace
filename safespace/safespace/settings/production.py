from .base import *

DEBUG = False

ALLOWED_HOSTS = ["127.0.0.1", "localhost", ".pythonanywhere.com"]

# PythonAnywhere serves HTTPS through a proxy; trust its header so
# request.build_absolute_uri() returns https:// links
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
