#!/usr/bin/env python3
"""Log in as an admin and fetch the protected completion timeline API."""

import os
from urllib.parse import urljoin

import requests

BASE_URL = os.environ.get("SAFESPACE_BASE_URL", "http://127.0.0.1:8000")
ADMIN_USERNAME = os.environ.get("SAFESPACE_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("SAFESPACE_ADMIN_PASSWORD", "admin")
API_URL = urljoin(BASE_URL.rstrip("/") + "/", "api/completion-timeline/")
LOGIN_URL = urljoin(BASE_URL.rstrip("/") + "/", "login/")


def login_as_admin(session):
    login_page = session.get(LOGIN_URL, timeout=10)
    login_page.raise_for_status()

    csrf_token = login_page.cookies.get("csrftoken")
    headers = {}
    if csrf_token:
        headers["X-CSRFToken"] = csrf_token
        headers["Referer"] = LOGIN_URL

    payload = {
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
        "next": "/api/completion-timeline/",
    }

    response = session.post(LOGIN_URL, data=payload, headers=headers, timeout=10)
    response.raise_for_status()

    if response.history:
        print("Login redirect received; session likely authenticated.")


def main():
    session = requests.Session()

    try:
        login_as_admin(session)
        response = session.get(API_URL, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Failed to fetch admin timeline from {API_URL}: {exc}")
        print("Make sure the app is running and the admin user exists.")
        return 1

    data = response.json()
    print(f"Fetched {len(data)} completion records from the timeline API.")

    for row in data[:10]:
        print(row)

    if len(data) > 10:
        print("... showing only the first 10 rows")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
