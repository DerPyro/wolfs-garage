"""Synthetic fixed-clock WSGI app for real-browser inspection acceptance only."""
import os
from datetime import date

from wolfs_garage.api import create_app


app = create_app({
    "GARAGE_DB": os.environ.get("GARAGE_DB", "data/garage.sqlite3"),
    "GARAGE_PUBLIC_ORIGIN": os.environ.get("GARAGE_PUBLIC_ORIGIN", "http://127.0.0.1:18988"),
    "GARAGE_TODAY_PROVIDER": lambda: date(2026, 10, 1),
})
